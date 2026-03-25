import pandas as pd
import re
import os
import json
from openai import OpenAI


def extract_dependencies(field_name):
    """解析字段依赖关系，支持多种条件前缀"""
    dependencies = {}

    # 定义支持的条件前缀列表
    condition_prefixes_yes = ["若有", "若存在", "若曾", "若罹患"]
    condition_prefixes_no = ["若无"]
    # 检查字段名是否包含任何条件前缀
    for prefix in condition_prefixes_yes:
        # 构建带括号的条件模式，如"（若有"
        pattern_str = f"（{prefix}(.+?)）"#从“prefix”开始匹配，进行非贪婪匹配，直到匹配到“）”结束，比如"（若有高血压）最高达"，匹配出"高血压"
        # 使用正则表达式匹配
        match = re.search(pattern_str, field_name)
        if match:
            # 提取括号内的疾病/条件名称
            condition_name = match.group(1)# match.group(1)：获取正则表达式中括号内匹配的内容，比如“高血压”
            # 构建父字段名称（根据前缀类型）
            if prefix == "若曾":
                parent_field = "是否曾患" + condition_name
            else:
                parent_field = "当前有无" + condition_name

            # 设置依赖关系
            dependencies = {
                'parent': parent_field,
                'condition': '是'  # 默认激活条件
            }
            break  # 找到匹配后退出循环

    for prefix in condition_prefixes_no:
        pattern_str = f"（{prefix}(.+?)）"

        # 使用正则表达式匹配
        match = re.search(pattern_str, field_name)
        if match:
            # 提取括号内的疾病/条件名称
            condition_name = match.group(1)

            # 构建父字段名称（根据前缀类型）
            if prefix == "若曾":
                parent_field = "是否曾患" + condition_name
            else:
                parent_field = "当前有无" + condition_name

            # 设置依赖关系
            dependencies = {
                'parent': parent_field,
                'condition': '否'  # 默认激活条件
            }
            break  # 找到匹配后退出循环
    return dependencies


def load_excel_template(file_path):
    """读取Excel文件并提取关键信息"""
    # 读取Excel文件
    df = pd.read_excel(file_path, sheet_name="Sheet1")

    # 创建空字典存储字段信息
    field_info = {}

    # 遍历每一行
    for index, row in df.iterrows():
        # 获取字段名称
        field_name = row['填写内容']

        # 跳过空行
        if pd.isna(field_name):
            continue
        # 获取字段描述和示例
        description = row['字段含义']
        example = row['示例'] if '示例' in row and not pd.isna(row['示例']) else ""

        # 解析依赖关系
        dependencies = extract_dependencies(field_name)
        # 存储字段信息，这是一个嵌套结构，field_name是一个键，里面的值就是 {}内部的值，但是{}里面又分出来三个键
        #分别是'描述'，'示例'，'依赖'，冒号也就是“：”后面的就是他们的值。
        #field_info是一级字典，{}里面的内容是二级字典，访问字典的某个字段的方式为：字典[键]
        #给某个键赋值的方法就是下面这个方法，如果只是单一结构，那只需要ield_info['症状'] = '头痛'，嵌套的话就得用大括号{}了
        field_info[field_name] = {
            '描述': description,
            '示例': example,
            '依赖': dependencies
        }

    return field_info


class FieldStateTracker:
    def __init__(self, template_data):#template_data是个字典，存储了所有信息
        # 1. 存储所有字段的模板信息
        self.template = template_data

        # 2. 存储已收集的字段数据，filled_data={}是创建了一个字典，如果是[],那就是创建了一个列表。
        self.filled_data = {}

        # 3. 待处理字段队列（初始包含所有字段）
        self.pending_fields = list(template_data.keys())#获取字典的所有键(key)，也就是第一列所有，是一个组

        # 4. 存储对话历史，，注：创建了一个列表,该字典同时存储着两种日志，分别是对话内容的日志，以及对话记录的日志。
        #对话内容有role和content两个key，对话记录则有field，value和evidence三个key，
        self.dialogue_history = []

    def get_next_field(self):
        """获取下一个需要提问的字段"""
        # 5. 遍历待处理字段
        for field in self.pending_fields:       #field就是每一个key
            # 6. 获取字段的依赖关系
            dependencies = self.template[field]["依赖"]

            # 7. 检查是否有依赖
            if dependencies:                    #如果有，dependencies就不是空的，就会运行下面的内容
                parent = dependencies["parent"] #在之前注释里，
                condition = dependencies["condition"]

                # 8. 检查父字段是否满足条件
                if parent in self.filled_data:#filled_data中的parent父字段看看是否已经填了，填了则运行下面的if
                    if self.filled_data[parent]["value"] == condition:#
                        return field  # 9. 如果condition条件满足，比如：condition=“是”，返回该字段进行处理
                else:
                    # 10. 父字段未回答，先处理父字段
                    return parent
            else:
                # 11. 无依赖关系，直接返回该字段
                return field

        # 12. 所有字段都已处理
        return None

    def update_field(self, field, value, evidence=None):#已知某一个字段field被填充，填充值为value，现在移除该字段所以进行的操作。
        """更新字段状态"""
        # 13. 存储字段值， # value为字段field对应的值，# evidence为原始对话文本（用于审计和追溯），如果没有，就用""而不是空字符去代替
        #举个例子：{"field": "症状", "value": "头痛", "evidence": "最近三天一直头痛"},
        self.filled_data[field] = {
            "value": value,
            "evidence": evidence or ""
        }

        # 14. 从待处理字段pending_fields中移除该字段
        if field in self.pending_fields:
            self.pending_fields.remove(field)

        # 15. 添加对话记录
        self.dialogue_history.append({
            "field": field,
            "value": value,
            "evidence": evidence
        })

    def add_dialogue(self, role, content):
        """添加对话记录"""
        # 16. 存储对话内容
        self.dialogue_history.append({
            "role": role,  # "system"、"AI"或"patient"
            "content": content
        })
    #如果value有值，比如175cm
    def get_field_value(self, field):
        """获取字段的值"""
        # 17. 返回字段的值（如果存在）
        if field in self.filled_data:
            return self.filled_data[field]["value"]
        return None

######



# 初始化 OpenAI 客户端
client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

# generate_question是一个生成问题的函数，系统角色设定为医疗随访助手，return模型生成的第一个回复内容
def generate_question(field, metadata, history):
    """生成针对性提问"""
    # 构建提示词
    prompt = f"""
    你是一名医疗随访助手，需要收集患者健康信息。
    当前需要获取：{metadata[field]['描述']}
    参考提问方式：{metadata[field]['示例']}

    已有信息：{history}

    请生成一个自然的问题：
    """

    # 调用 API
    completion = client.chat.completions.create(
        model="qwen-plus",
        messages=[
            {"role": "system", "content": "你是一名专业的医疗随访助手"},
            {"role": "user", "content": prompt}
        ]
    )

    # 返回生成的文本
    return completion.choices[0].message.content.strip()

# 解析答案函数，系统角色设定为数据解析助手，尝试解析返回的 JSON 内容，
def parse_answer(field, answer, history):
    """解析患者回答并提取结构化数据"""
    # 构建提示词
    prompt = f"""
    根据以下对话历史，提取结构化信息：
    {history}

    当前需要提取：{field}
    提取要求：{metadata[field]['描述']}

    患者最新回答："{answer}"

    请按JSON格式输出：
    {{"field_value": "提取的值", "confidence": 0-1}}
    """

    # 调用 API
    completion = client.chat.completions.create(
        model="qwen-plus",
        messages=[
            {"role": "system", "content": "你是一名医疗数据解析助手"},
            {"role": "user", "content": prompt}
        ]
    )

    # 解析 JSON 结果
    try:
        result = json.loads(completion.choices[0].message.content.strip())
        return result
    except json.JSONDecodeError:
        # 解析失败时返回默认值
        return {"field_value": "", "confidence": 0.0}


def main_flow(excel_path):
    # 初始化组件
    metadata = load_excel_template(excel_path)
    tracker = FieldStateTracker(metadata)
    dialogue_history = []

    # 对话循环
    while field := tracker.get_next_field():
        # 生成问题
        question = generate_question(field, metadata, dialogue_history)
        print(f"AI: {question}")
        dialogue_history.append(("AI", question))

        # 获取回答
        answer = input("Patient: ")
        dialogue_history.append(("Patient", answer))

        # 解析并更新状态
        result = parse_answer(field, answer, dialogue_history)
        if result['confidence'] > 0.7:  # 置信度阈值
            tracker.update_field(field, result['field_value'], answer)

    # 输出结果
    print(generate_markdown_report(tracker.filled_data))

main_flow("../form.xls")

######