import pandas as pd
import re
import os
import json
from openai import OpenAI
from state_tracking import *


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

    当前需要收集的信息：{metadata[field]['描述']}
    参考提问方式：{metadata[field]['示例'] or  "无"}
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
    # 这里只需要知道，如果想返回ai输出的原始结果，只需要return completion.choices[0].message.content即可，下面解释以下各个字段意思
    # completion: API调用返回的响应对象
    # choices: 包含模型生成结果的列表（通常一个请求对应一个结果）
    # [0]: 获取列表中的第一个（通常也是唯一的）响应结果
    # .message：访问响应对象中的消息部分，包含AI生成的回复内容
    # .strip()字符串方法，移除字符串两端的空白字符，作用为确保没有多余的换行符、空格等干扰JSON解析   示例：" \n 你好 \t " → "你好"
    # json.loads(...)  核心函数：将JSON格式的字符串转换为Python数据结构，当然这里没有用，后面设定医疗解析助手时用到了。
    return completion.choices[0].message.content.strip()
# 解析答案函数，系统角色设定为数据解析助手，负责跟据对话内容提取要填写的东西，尝试解析返回的 JSON 内容，
#解析助手输入进去当前字段名field，患者的回答内容answer，整个数据集：metadata，AI和患者的整个对话记录history_text
def parse_answer(field, answer, metadata, history):
    """解析患者回答并提取结构化数据"""
    # 构建提示词
    prompt = f"""
    根据以下对话历史，提取结构化信息：
    {history}
    当前需要提取：{field}
    提取要求：{metadata[field]['描述']}
    患者最新回答："{answer}"
    请严格按以下JSON格式输出结果，不要包含任何额外文本、代码块标记或解释：
    {{"field_value": "提取的值", "confidence": 0-1}}
     JSON格式输出具体要求：
    1. field_value 应是文本提取结果，为字符串格式
    2. confidence 是置信度评分(0.0-1.0)，是浮点数
    3. 不要包含任何额外文本或解释
    4. 确保是有效的JSON格式
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
    try:#以下有try和except代码的解释。
        raw_result = completion.choices[0].message.content
            # 这里的原因是因为模型返回的是'```json\n{"field_value": "175cm", "confidence": 1.0}\n```'的式的内容，
            # 但是json.loads()括号中输入的内容希望是以“{”开头，以“}”结尾的，如果直接将值送到json.loads，就会出现下面json.JSONDecodeError式的错误。
            # 因此我们采用re.sub(r'^```json\n|\n```$', '', raw_result).strip()删除开头与结尾的'```json\n这些东西然后再送到json.loads()中
        clean_result = re.sub(r'^```json\n|\n```$', '', raw_result).strip()
            # json.loads(...)  核心函数：将JSON格式的字符串转换为Python数据结构，在这里是将字符串转变为字典类型，这样后面才能用result['field_value']去调用值，
        re_result = json.loads(clean_result)
        print("clean_result的值为", clean_result)
        return re_result
        #(json.JSONDecodeError, KeyError) as e:的意思是捕获圆括号中的这组异常中的任意一种并赋值给e
        #json.JSONDecodeError含义：当 json.loads() 尝试解析无效 JSON 字符串时会出现的异常，
        #   这种异常一般是因为字符串不是有效的 JSON 格式或者模型返回了非 JSON 内容（如自然语言解释）
        #KeyError含义：当尝试访问字典中不存在的键时出现的异常
        #   这种异常一般是因为模型返回了 JSON 的内容，但并没有按照 {{"field_value": "提取的值", "confidence": 0-1}}的要求去返回
    except (json.JSONDecodeError, KeyError) as e:
        raw_content = completion.choices[0].message.content
        print(f"解析答案出错: {e}")
        print(f"加了strip并显示不可见字符的原始内容: {repr(raw_content.strip())}")  # 使用repr显示不可见字符
        clean_content = re.sub(r'^```json\n|\n```$', '', raw_content).strip()
        print("clean_content的值为",clean_content)
        return {"field_value": "", "confidence": 0.0}
    except Exception as e:
        print(f"API调用出错: {e}")
        return {"field_value": "", "confidence": 0.0}



def main_flow(excel_path):
    """主流程函数"""
    # 初始化组件
    metadata = load_excel_template(excel_path)
    tracker = FieldStateTracker(metadata)

    # 问候语
    tracker.add_dialogue("AI", "您好，我是医疗随访助手，需要了解您的健康状况。")
    print("AI: 您好，我是医疗随访助手，需要了解您的健康状况。")

    # 对话循环
    while True:
        field = tracker.get_next_field()
        if field is None:
            print("AI: 所有信息已收集完成，感谢您的配合！")
            break

        # 获取对话历史文本
        history_text = tracker.get_conversation_text()   #读取dialogue_history列表中AI和patient之前的所有对话记录

        # 生成问题
        question = generate_question(field, metadata, history_text) #开始对话，由ai发起
        tracker.add_dialogue("AI", question)   #将AI说的话存在类tracker的dialogue_history列表中
        print(f"AI: {question}")
        print("当前正处在的要回答的问题位置为", field)
        # 获取用户回答
        answer = input("Patient: ")
        tracker.add_dialogue("Patient", answer) ##将患者patient说的话存在类tracker的dialogue_history列表中
        # 给解析助手输入进去当前字段名field，患者的回答内容answer，整个数据集：metadata，AI和患者的整个对话记录history_text
        result = parse_answer(field, answer, metadata, history_text)
        # 处理解析结果
        if result['confidence'] > 0.6:
            tracker.update_field(field, result['field_value'], answer)
            print(f"AI: 已记录: {field} = {result['field_value']}")
        else:
            print(f"AI: 抱歉，我未能理解您的回答，请再说明一下{field}的情况。")

main_flow('../2025.5.28人工智能供者随访计划excel版.xls')
