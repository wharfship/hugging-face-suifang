import pandas as pd
from collections import defaultdict


def load_excel_template(file_path):
    """解析Excel模板结构"""
    df = pd.read_excel(file_path, sheet_name="Sheet1")

    # 构建字段元数据
    field_metadata = {}
    for _, row in df.iterrows():
        field = row['填写内容']
        if pd.isna(field):
            continue

        field_metadata[field] = {
            'description': row['字段含义'],
            'example': row.get('示例', ''),
            'dependencies': extract_dependencies(field)  # 解析条件依赖
        }
    return field_metadata


def extract_dependencies(field_name):
    """解析字段依赖关系（如高血压相关字段）"""
    dependencies = {}
    if "（若有" in field_name:
        # 示例：解析出依赖父字段为'当前有无高血压'
        base_field = re.search(r"（若有(.+?)）", field_name).group(1)
        dependencies = {'parent': f'当前有无{base_field}', 'condition': '是'}
    return dependencies


class FieldStateTracker:
    def __init__(self, metadata):
        self.metadata = metadata
        self.filled_data = defaultdict(dict)
        self.pending_fields = list(metadata.keys())

    def get_next_question(self):
        """获取下一个需要提问的字段（带条件检查）"""
        for field in self.pending_fields:
            deps = self.metadata[field].get('dependencies', {})

            # 检查条件依赖
            if 'parent' in deps:
                parent_value = self.filled_data.get(deps['parent'], {}).get('value')
                if parent_value != deps['condition']:
                    continue  # 条件不满足则跳过

            return field
        return None  # 所有字段完成

    def update_field(self, field, value, evidence):
        """更新字段状态"""
        self.filled_data[field] = {
            'value': value,
            'evidence': evidence,  # 存储原始对话片段
            'timestamp': datetime.now()
        }
        self.pending_fields.remove(field)


import dashscope

dashscope.api_key = "YOUR_API_KEY"


def generate_question(field, metadata, history):
    """调用Qwen3生成针对性提问"""
    prompt = f"""
    你是一名医疗随访助手，需要收集患者健康信息。
    当前需要获取：{metadata[field]['description']}
    参考提问方式：{metadata[field]['example']}

    已有信息：
    {format_collected_data(history)}

    请生成一个自然的问题：
    """

    response = dashscope.Generation.call(
        model='qwen-plus',
        prompt=prompt,
        max_length=500
    )
    return response.output.text


def parse_answer(field, answer, history):
    """解析患者回答并提取结构化数据"""
    prompt = f"""
    根据以下对话历史，提取结构化信息：
    {history[-3:]}  # 最近3轮对话

    当前需要提取：{field}
    提取要求：{metadata[field]['description']}

    患者最新回答："{answer}"

    请按JSON格式输出：
    {{"field_value": "提取的值", "confidence": 0-1评分}}
    """

    response = dashscope.Generation.call(
        model='qwen-max',
        prompt=prompt,
        temperature=0.2  # 降低随机性
    )
    return json.loads(response.output.text)


def main_flow(excel_path):
    # 初始化组件
    metadata = load_excel_template(excel_path)
    tracker = FieldStateTracker(metadata)
    dialogue_history = []

    # 对话循环
    while field := tracker.get_next_question():
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
