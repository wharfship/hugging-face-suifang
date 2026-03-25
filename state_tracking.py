import sys
import re
import os
import json
from openai import OpenAI
from statistic_preprocessing import *
from Model_initialization import *

class FieldStateTracker:
    def __init__(self, template_data):#template_data是个字典，存储了所有信息
        # 1. 存储所有字段的模板信息
        self.template = template_data

        # 2. 存储已收集的字段数据，filled_data={}是创建了一部字典，如果是[],那就是创建了一个列表。
           #get_field_value(field)和get_field_status(field)可以获取里面具体的值
        self.filled_data = {}

        # 3. 待处理字段队列（初始包含所有字段）
        self.pending_fields = list(template_data.keys())#获取字典的所有键(key)，也就是第一列所有，是一个组

        # 4. 存储对话历史，包括对话内容和对话记录，后续传给问题助手和医疗数据解析助手
        #对话内容有role和content两个key，对话记录则有field，value和evidence三个key，
        self.dialogue_history = []
        # 5. 存储解析内容，用来后面打印出excel形式
        self.parse_history = []

    #get_next_field用于输出下一个需要填写的字段
    def get_next_field(self):
        """获取下一个需要提问的字段"""
        # 5. 遍历待处理字段
        for field in self.pending_fields:       #field就是每一个key
            # 6. 获取字段的依赖关系
            dependencies = self.template[field]["依赖"]
            # 7. 检查是否有依赖
            if dependencies:                    #如果有，dependencies就不是空的，就会运行下面的内容
                parent = dependencies["parent"] #在之前注释里，
                condition = dependencies.get("condition","不存在")
                opposite_condition = dependencies.get("opposite_condition","不存在")
                if condition != "不存在" and self.filled_data[parent]["value"] in condition :
                    return field  # 9. 如果condition条件满足，比如：condition=“是”，返回该字段进行处理
                elif opposite_condition != "不存在" and self.filled_data[parent]["value"] not in opposite_condition:
                    return field
                # else:
                #     self.parse_history.append({
                #         "field": field,
                #         "value": "",
                #         # "evidence":evidence1,
                #         "status":"",
                #     })
                #     if field in self.pending_fields:
                #         self.pending_fields.remove(field)
            else:
                # 11. 无依赖关系，直接返回该字段
                return field

        # 12. 所有字段都已处理
        return None

    def update_field(self, field, result, evidence=None):#保存字段的value，evidence的值，移除该字段,再将对话添加到历史记录里
        """更新字段状态"""
        # 13. 存储字段值， # value为字段field对应的值，# evidence为原始对话文本（用于审计和追溯），如果没有，就用""而不是空字符去代替
        #举个例子：{"field": "症状", "value": "头痛", "evidence": "最近三天一直头痛"},
        #evidence1 = evidence if evidence is not None else result["evidence"]
        evidence1 = None
        self.filled_data[field] = {
            "value": result['field_value'],
            #"evidence": result["evidence"] or "",
            "evidence": evidence1,
            "status": result['status']
        }
        # 14. 从待处理字段pending_fields中移除该字段
        if field in self.pending_fields:
            self.pending_fields.remove(field)

        # 15. 添加到解析表里，用来后续打印保存
        self.parse_history.append({
            "field": field,
            "value": result['field_value'],
            #"evidence":evidence1,
            "status": result['status']
        })

    def add_dialogue(self, role, content):
        """添加对话记录"""
        # 16. 存储对话内容
        self.dialogue_history.append({
            "role": role,  # role是"AI"或"patient"
            "content": content #
        })
    #如果value有值，比如175cm
    def get_field_value(self, field):
        """获取字段的值"""
        if field in self.filled_data:
            return self.filled_data[field]["value"]
        return None
    def get_field_status(self, field):
        """获取字段的状态"""
        if field in self.filled_data:
            return self.filled_data[field]["status"]
        return None

    def get_conversation_text(self):
        """获取对话文本历史"""
        conversation = []
        for entry in self.dialogue_history:
            if "role" in entry:
                prefix = "AI: " if entry["role"] == "AI" else "Patient: "
                conversation.append(f"{prefix}{entry['content']}")
        return "\n".join(conversation)

    def get_dialogue_history(self):
        """获取对话和解析文本历史"""
        return self.dialogue_history

    def get_parse_history(self):
        """获取解析文本历史"""
        return self.parse_history




######

#


######
# import dashscope
#
# dashscope.api_key = "YOUR_API_KEY"
#
#
# def generate_question(field, metadata, history):
#     """调用Qwen3生成针对性提问"""
#     prompt = f"""
#     你是一名医疗随访助手，需要收集患者健康信息。
#     当前需要获取：{metadata[field]['description']}
#     参考提问方式：{metadata[field]['example']}
#
#     已有信息：
#     {format_collected_data(history)}
#
#     请生成一个自然的问题：
#     """
#
#     response = dashscope.Generation.call(
#         model='qwen-plus',
#         prompt=prompt,
#         max_length=500
#     )
#     return response.output.text
#
#
# def parse_answer(field, answer, history):
#     """解析患者回答并提取结构化数据"""
#     prompt = f"""
#     根据以下对话历史，提取结构化信息：
#     {history[-3:]}  # 最近3轮对话
#
#     当前需要提取：{field}
#     提取要求：{metadata[field]['description']}
#
#     患者最新回答："{answer}"
#
#     请按JSON格式输出：
#     {{"field_value": "提取的值", "confidence": 0-1评分}}
#     """
#
#     response = dashscope.Generation.call(
#         model='qwen-max',
#         prompt=prompt,
#         temperature=0.2  # 降低随机性
#     )
#     return json.loads(response.output.text)