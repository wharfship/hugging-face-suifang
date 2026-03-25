import json
import re

import pandas as pd
from openai import OpenAI

from field_rules import build_field_rule_prompt
from state_tracking import FieldStateTracker
from statistic_preprocessing import load_excel_template


client = OpenAI(
    api_key="sk-c52fb472f73a464cab9eee6f9eb07f19",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)


def _append_field_specific_guidance(prompt, field):
    # simple 版仍然使用字段规则，但不再让模型返回解释和依据。
    rule_prompt = build_field_rule_prompt(field)
    if not rule_prompt:
        return prompt
    return f"{prompt}\n{rule_prompt}\n"


def generate_question(field, metadata, history, status="first_ask"):
    """生成针对性提问"""
    prompt = f"""
    你是一名医疗随访助手，需要继续完成患者随访。

    当前字段：{field}
    字段要求：{metadata[field]['描述']}
    参考提问方式：{metadata[field]['示例'] or '无'}
    已有对话：{history}
    当前流程状态：{status}

    请只生成下一句最合适的问题。
    规则：
    1. 如果状态是 ask_again，只围绕仍缺失的核心信息补问，不重复已经确认的内容。
    2. 如果患者已经提供了核心信息，即使措辞是“大概”“差不多”，也不要继续追求过细精度。
    3. 问句要自然、简洁、口语化，不要写开场白。
    4. 对复杂字段，可以拆成一个更容易回答的小问题，但一次只问当前最关键的一步。
    5. 如果字段是是/否类问题，用最直接的问法。
    6. 如涉及时间，当前时间按 2025 年 10 月 30 日理解。
    """

    prompt = _append_field_specific_guidance(prompt, field)

    completion = client.chat.completions.create(
        model="qwen-plus",
        messages=[
            {"role": "system", "content": "你是一名专业的医疗随访助手"},
            {"role": "user", "content": prompt}
        ]
    )
    return completion.choices[0].message.content.strip()


# simple 版只让模型输出最少的结构化结果，减少 token 和推理负担。
def parse_answer(field, answer, description, history):
    """解析患者回答并提取结构化数据"""
    prompt = f"""
    你是一名医疗数据解析助手。请根据当前字段要求和对话历史，提取可写入 Excel 的结果，并判断当前字段是否还需要继续追问。

    当前字段：{field}
    字段要求：{description}
    对话历史：{history}
    患者本轮回答：{answer}

    请只输出 JSON：
    {{
      "status": "done|ask_again|later|manual_review",
      "completion": "complete|partial|empty",
      "field_value": "提取后的值",
      "confidence": 0-1
    }}

    判定规则：
    1. status 只表示流程动作：
       - done: 当前字段可以结束。
       - ask_again: 当前字段还值得继续问一次。
       - later: 患者明确表示稍后补充、上传检查单/报告/图片后再判断。
       - manual_review: 出现明显冲突、异常或不适合自动判断的情况。
    2. completion 只表示信息完整度：complete / partial / empty。
    3. 不要把“大概、差不多、应该”自动判成 ask_again；只要核心信息够填表，优先输出 done + complete。
    4. 对复合问题，如果患者已经回答了一部分，就保留已回答内容到 field_value 中。
    5. 单位自动标准化，如斤转 kg、米转 cm。
    6. field_value 只写适合落表的结果，不写建议、不写解释。
    7. 如涉及时间，当前时间按 2025 年 10 月 30 日理解。
    """

    prompt = _append_field_specific_guidance(prompt, field)

    completion = client.chat.completions.create(
        model="qwen-plus",
        messages=[
            {"role": "system", "content": "你是一名医疗数据解析助手"},
            {"role": "user", "content": prompt}
        ]
    )

    try:
        raw_result = completion.choices[0].message.content
        clean_result = re.sub(r'^```json\s*|```$', '', raw_result).strip()
        parsed_result = json.loads(clean_result)
        print(f"解析结果：{parsed_result.get('field_value', '')}  置信度：{parsed_result.get('confidence', 0)}")
        return parsed_result
    except (json.JSONDecodeError, KeyError) as e:
        print(f"解析答案出错: {e}")
        return {
            "status": "ask_again",
            "completion": "empty",
            "field_value": "",
            "confidence": 0.0,
        }
    except Exception as e:
        print(f"API调用出错: {e}")
        return {
            "status": "ask_again",
            "completion": "empty",
            "field_value": "",
            "confidence": 0.0,
        }
