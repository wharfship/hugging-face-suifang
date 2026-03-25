# 修改说明文档

## 1. 这次修改主要解决了什么

这次修改主要围绕两个问题展开：

1. 原来的 `status` 既承担“流程控制”又承担“信息完整度”的职责，导致模型很难稳定判断，所以 prompt 越写越长。
2. Excel 模板中的 `追问上限` 已经在预处理里读出来了，但主流程没有真正使用，仍然写死成了固定次数。
3. 前端界面的状态展示和返回链路有混淆，聊天区、当前字段、生成问题这几部分职责不够清晰。

现在的整体思路是：

- 用 `status` 只表示“流程动作”
- 用 `completion` 只表示“信息完整度”
- 用 `追问上限` 真正控制字段是否继续追问
- 聊天区负责展示 AI 的真实提问
- “当前字段” Textbox 只负责显示当前正在采集哪个字段

---

## 2. 新增文件：`workflow_status.py`

## 2.1 新增文件：`field_rules.py`

文件：`field_rules.py`

### 修改逻辑

这个文件是这次新增的“字段规则层”。

它的作用是：

- 不再把“什么叫核心信息够填表”全部压给模型自己判断
- 先让模型提取结果
- 再由代码按字段规则做一次校正

### 修改成什么样

核心入口有两个：

```python
def build_field_rule_prompt(field):
```

它会把字段级规则转成 prompt 附加给模型。

```python
def apply_field_completion_rules(field, result):
```

它会在模型输出之后，再按字段规则把结果收束成更贴近医院表单的状态。

### 为什么这样做

因为“核心信息是否足够”本质上是医院填表规则，不应该完全依赖模型主观判断。

例如：

- `当前身高`：有一个大致数值就够
- `当前血压`：有一组可写入的血压值就够
- `其余病史及用药情况`：如果回答“无”就可以结束；如果回答“有”，至少要有病名
- `手术切口疼痛持续时间`：模糊时长如“术后至今”“间断出现”也可接受

这层规则放到代码里后，比继续堆 prompt 更稳定，也更方便你后续自己维护。

### 代码位置

- 规则表定义：`field_rules.py`
- prompt 生成：`field_rules.py`
- 结果校正：`field_rules.py`


文件：`workflow_status.py`

### 修改逻辑

这个文件是新加的状态机工具层，目的是把“模型输出”和“主流程消费”之间隔开。

原来的问题是：

- 模型输出很多状态：`success / partial_success / ambiguous / skip / pending / escalate`
- 这些状态本身语义有重叠
- 主流程并没有完整消费这些状态
- 导致模型即使做出了细分，代码侧也不一定真的按这个细分执行

所以我新建了一个统一状态层。

### 修改成什么样

核心代码：

```python
CANONICAL_STATUSES = {"done", "ask_again", "later", "manual_review"}
COMPLETION_LEVELS = {"complete", "partial", "empty"}
```

含义变成：

- `done`：当前字段可以先结束
- `ask_again`：当前字段还值得再追问一次
- `later`：患者明确说后续补材料
- `manual_review`：当前字段不适合自动完成，需要人工复核

同时把信息完整度单独拆出来：

- `complete`：够填表
- `partial`：拿到了一部分
- `empty`：基本没拿到有效信息

### 为什么这么做

这样做的核心原因是把两种不同任务拆开：

- 一个是“这个字段现在要不要继续问”
- 一个是“这个字段已经拿到了多少信息”

以前这两个问题都压在一个 `status` 里，所以模型很容易不稳定。拆开之后，模型的判断空间更清晰，主流程也更容易写。

### 兼容旧状态

为了不让你之前的 prompt 或返回结果完全失效，我保留了兼容映射：

```python
LEGACY_STATUS_MAPPING = {
    "success": ("done", "complete"),
    "partial_success": ("ask_again", "partial"),
    "ambiguous": ("ask_again", "empty"),
    "skip": ("done", "empty"),
    "pending": ("later", "empty"),
    "escalate": ("manual_review", "partial"),
}
```

对应代码位置：`workflow_status.py`

### 追问上限接入

这里也统一加了提问上限读取：

```python
def get_field_attempt_limit(metadata, field, default=2):
    field_meta = metadata.get(field, {})
    raw_limit = field_meta.get("追问上限", default)
```

以及追问达到上限后的收口逻辑：

```python
def finalize_after_attempt_limit(result):
    finalized = dict(result)
    finalized["status"] = "done"
```

这么做的原因是：达到追问上限时，主流程必须有一个一致的收口行为，而不是散落在多个 `if` 分支里。

---

## 3. 修改文件：`state_tracking.py`

文件：`state_tracking.py`

### 修改逻辑

这个文件现在专门负责字段状态存储，不再和模型层互相缠绕。

原来的问题主要有两个：

1. `evidence` 实际上没有被保存，之前直接写成了 `None`
2. `completion / reasoning` 这些对后续调试很有帮助的信息没有落到状态里

### 修改成什么样

现在 `update_field()` 会把一个字段的完整结果都存下来：

```python
def update_field(self, field, result, evidence=None):
    evidence_text = evidence if evidence is not None else result.get("evidence", "")
    completion = result.get("completion", "")
    reasoning = result.get("reasoning", "")
```

并在 `filled_data` 和 `parse_history` 两边都保留：

```python
self.filled_data[field] = {
    "value": result.get("field_value", ""),
    "evidence": evidence_text,
    "status": result.get("status", ""),
    "completion": completion,
    "reasoning": reasoning,
}
```

### 为什么这么做

原因很直接：

- 之后你调试模型判断时，需要知道“它为什么结束了这个字段”
- 你导出 Excel 时，也希望看到更完整的过程信息
- 以后如果做人工复核，`reasoning` 和 `evidence` 也能直接拿来用

### 依赖字段推进逻辑也做了收敛

`get_next_field()` 现在写得更稳一些，会先检查父字段是否已经存在，再决定是否进入条件字段：

```python
if parent not in self.filled_data:
    continue
```

这样可以避免依赖字段在父字段还没落盘时就被误访问。

---

## 4. 修改文件：`Model_initialization.py`

文件：`Model_initialization.py`

### 修改逻辑

这里主要改了两件事：

1. `generate_question()` 的提示词，改成围绕“当前流程状态”来提问
2. `parse_answer()` 的输出结构，改成新的状态机格式

### 4.1 `generate_question()` 怎么改的

现在问句生成不再围绕旧的 `success / partial_success / ambiguous` 去写，而是围绕更稳定的动作状态：

```python
def generate_question(field, metadata, history, status="first_ask"):
```

关键规则是：

```python
1. 如果状态是 ask_again，只围绕仍缺失的核心信息补问，不重复已经确认的内容。
2. 如果患者已经提供了核心信息，即使措辞是“大概”“差不多”，也不要继续追求过细精度。
```

### 为什么这样做

你的原始 prompt 最大的问题不是“不够长”，而是模型在做两件事：

- 判断当前字段要不要继续
- 同时决定下一轮要怎么问

我现在先把流程判断收束成少量状态，再让生成问题只关心怎么继续问，这样生成质量会稳很多。

### 4.2 `parse_answer()` 怎么改的

现在模型输出格式变成：

```python
{
  "status": "done|ask_again|later|manual_review",
  "completion": "complete|partial|empty",
  "field_value": "提取后的值",
  "confidence": 0-1,
  "reasoning": "一句话说明判断依据",
  "evidence": "与当前字段最相关的关键对话"
}
```

### 为什么这样做

因为原来的 `partial_success` 本质上混合了两层意思：

- 已经提取到部分信息
- 还要不要继续追问

现在把它拆开后，模型更容易稳定输出，代码也更容易消费。

### 字段特殊规则保留，但方式更收敛

原来很多字段规则是散着写的，我保留了这些业务知识，但统一收束到：

```python
def _append_field_specific_guidance(prompt, field):
```

例如是/否字段：

```python
if field in YES_NO_FIELDS:
    prompt += """
    特别注意：这是简单的是/否字段。
    - 若患者表达肯定，field_value输出“是”
    - 若患者表达否定，field_value输出“否”
    - 若无法判断，field_value输出“未知”
    """
```

这样做的原因是：你原本的 prompt 很多是有价值的业务经验，不应该删掉；但应该按“通用规则 + 字段特例”的方式组织，而不是越堆越散。

---

## 5. 修改文件：`ggg.py`

文件：`ggg.py`

这是这次改动最多的文件，因为它承担了主流程。

### 5.1 导出列改了什么

我先把导出字段扩充了：

```python
COLUMN_NAMES = {
    "field": "填写内容",
    "value": "填写数据",
    "completion": "完整度",
    "status": "流程状态",
    "reasoning": "解释",
    "evidence": "数据原始依据",
}
```

### 为什么这样做

因为现在状态不只是一个 `status`，而是 `status + completion + reasoning + evidence` 一整套信息。你后面调试时，这些列会非常有用。

### 5.2 增加了统一导出函数

```python
def export_tracker_data():
```

### 为什么这样做

原来你在多个地方重复写：

- `DataFrame` 转换
- Excel 导出
- Excel 格式化

这些逻辑散在多个位置，后续很容易改漏。抽成一个函数后，主流程会清晰很多。

### 5.3 把确认消息抽成了独立逻辑

```python
def build_confirmation_message(field, result):
```

### 为什么这样做

因为现在字段结束的原因可能有好几种：

- 真正完整结束
- 部分结束
- 后续补充
- 人工复核

所以不适合再统一回复一句“好的”。现在会根据 `status/completion` 生成不同确认语。

### 5.4 BMI 改成本地计算

```python
def build_bmi_result():
```

### 为什么这样做

BMI 是确定公式问题，不应该再浪费一次模型调用。

本地计算好处是：

- 稳定
- 快
- 不消耗 token
- 不会受模型随机性影响

### 5.5 追问上限终于接入主流程

这一段是最关键的：

```python
attempt_limit = get_field_attempt_limit(metadata, field)
```

如果模型仍然输出 `ask_again`，就累计本字段提问次数：

```python
if result["status"] == "ask_again":
    field_attempts[field] = field_attempts.get(field, 0) + 1
```

达到上限后自动收口：

```python
if current_attempts >= attempt_limit:
    result = finalize_after_attempt_limit(result)
    tracker.update_field(field, result)
```

### 为什么这样做

这是为了真正把你在 `statistic_preprocessing.py` 里定义好的“字段复杂度”接到运行逻辑里。

例如：

- `当前有无高血压` 这类简单字段，只适合追问 1 次
- `（若有高血压）药物控制方案` 这种复合问题，可以追问 4 次

如果不接这个上限，模型再会判断，流程也还是不稳定。

### 5.6 前端返回链路修正

我前面还专门修了一次这里，因为你测试时出现了“回答后模型不继续提问”的现象。

问题根因是：

- 后端实际生成了 `question`
- 但返回给 `question_output` 的是 `field`
- 同时助手消息没有正确写回当前会话的 `chat_history`

所以我把这块职责重新理顺了：

```python
def add_assistant_message(message, current_chat_history):
    tracker.add_dialogue("AI", message)
    current_chat_history.append({"role": "assistant", "content": message})
```

以及：

```python
question = generate_question(field, metadata, history_text, status_for_question or "first_ask")
add_assistant_message(question, chat_history)
```

### 为什么这样做

因为 Gradio 前端是否显示“新问题”，取决于返回给组件的 `chat_history` 是否真的包含这条 AI 新消息，而不是只存在于全局变量里。

### 5.7 你刚刚提出的前端修改

### 5.8 当前字段 Textbox

现在前端这部分的职责重新明确了：

- 聊天框：显示 AI 真正提的问题
- `当前字段` Textbox：只显示当前正在采集的字段名

对应代码：

```python
question_output = gr.Textbox(label="当前字段")
```

以及初始化和每轮提交后，返回给这个 Textbox 的都是 `field` 而不是 `question`。

这样做的原因是：字段名和实际问句不是一回事，拆开后界面更清楚，也更方便调试字段流转。


你说：

- Textbox 标签不要叫“当前要回答的问题”
- 改成显示“当前字段”
- 里面内容也显示当前字段

我已经按这个要求改了：

```python
question_output = gr.Textbox(label="当前字段")
```

并且 `init_system()` 和 `process_user_input()` 现在返回给这个 Textbox 的都是 `field`，不是 `question`。

这样分工就变成：

- 聊天框：显示 AI 实际提问
- 当前字段 Textbox：显示当前正在填写哪个字段

这比之前更清晰。

---

## 6. 目前这套修改后的整体运行逻辑

现在主流程大致是：

1. 从 Excel 模板读出字段、字段描述、依赖关系、追问上限
2. 选出当前应该处理的字段
3. 模型解析本轮用户回答，输出 `status + completion + field_value`
4. 如果 `status == ask_again`，就看是否达到该字段自己的追问上限
5. 没达到就继续问，达到了就自动收口
6. 如果字段已经结束，就进入下一个字段
7. BMI 这类确定性字段由程序本地自动计算
8. 聊天框展示真实问答过程，“当前字段”单独显示当前采集字段

---

## 7. 还没有动的地方

这次我主要动了：

- `workflow_status.py`
- `state_tracking.py`
- `Model_initialization.py`
- `ggg.py`

暂时没有同步处理 `ggg_simple.py`，所以如果你后面还打算继续保留这个入口，建议下一步把它和 `ggg.py` 对齐，不然两个版本的行为会继续分叉。

另外，`api_key` 现在还在代码里硬编码，这个最好后面再单独收一轮，改成环境变量读取。
