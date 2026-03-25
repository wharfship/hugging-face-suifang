import pandas as pd
import re
import os
import json
from openai import OpenAI
from state_tracking import *


client = OpenAI(
    api_key="sk-c52fb472f73a464cab9eee6f9eb07f19",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
# generate_question是一个生成问题的函数，系统角色设定为医疗随访助手，return模型生成的第一个回复内容
def generate_question(field, metadata, history, status="None"):
    """生成针对性提问"""
    # 构建提示词
    prompt = f"""
    你是一名医疗随访助手，需要收集患者健康信息。

    当前需要收集的信息：{metadata[field]['描述']}
    参考提问方式：{metadata[field]['示例'] or  "无"}
    已经进行过的对话和提取出的信息：{history}
    当前问题状态：{status}
    
    1. 请生成一个自然的问题，避免过度追问细节。如果患者已提供足够信息，即使不完整也应考虑接受;
    2. 使用自然连贯的语气;
    3. 无需使用开场白类型的话，请直接进入;
    4. 对于复杂的或较为专业的问题，请给出适当示例，方便患者回答;
    5. 对于需要回答多个子问题的问题，并对要回答的小问题做字体加深处理;
    6. 患者即使使用了“大概”，“应该”等类似不确定的词语，也可判定为回答了问题，无需对该问题的精确度问题进行进一步追问
    7. 如有涉及时间问题，当前时间是2025年10月30日
    当前问题状态说明：
    - None: 当前问题是第一次提问
    - success: 患者已经回答了全部问题
    - partial_success: 患者回答了部分问题，或对提问进行了正常的回答，但当前问题还需要继续提问以补充信息
    - ambiguous: 患者当前回答比较模糊，没有回答该问题，需要澄清具体内容或重新询问
    - skip: 患者不愿提供此信息
    - pending: 患者明确承诺会上传相关医疗图片或其他数据体检相关数据（如化验单）
    - escalate: 需要人工干预的特殊情况
    """

    standardized_fields = [
        "当前有无糖尿病",
        "当前有无高血压",
        "是否曾患冠心病",
        "是否曾患脑血管病",
        "近一年是否存在手术切口疼痛"
    ]

    if field in standardized_fields:
        prompt += f"""
        特别注意：对于字段"{field}"，请遵循以下规则：
        - 只需简单询问患者是否有该情况，无需追问过多细节
        - 使用简单直接的问法，避免复杂医学术语
        """


    if field == "（若曾患脑血管病）具体疾病、治疗方式及有无后遗症":
        prompt += f"""
        特别注意：对于此字段，请遵循以下规则：
        - 只需提问到疾病类型、大致治疗方式和后遗症有无即可
        - 无需提问过于详细的治疗方式的治疗细节，了解大致方法(药物/手术/介入)即可
        """

    if field == "（若有糖尿病）药物控制方案":
        prompt += f"""
        特别注意：对于此字段，请遵循以下规则：
        - 无需过于详细的治疗方式的治疗细节，了解大致方法即可
        - 对于空腹血糖，无需询问过于详细的治疗细节，只需了解大致即可
        """

    if field == "具体疾病、治疗方式及有无后遗症":
        prompt += f"""
        特别注意：对于字段"{field}"，请遵循以下规则：
        - 只需询问大致疾病类型、大致治疗方式和后遗症有无
        - 无需询问过于详细的治疗细节，了解大致方法(药物/手术/介入)即可
        """

    if field == "近一年是否存在手术切口疼痛":
        prompt += f"""
        特别注意：对于字段"{field}"，请遵循以下规则：
        - 只需确认患者在近一年内是否有手术史及切口是否疼痛即可
        - 患者只需要提供大致时间，即可视为完整回答
        - 无需追问疼痛的具体程度、持续时间、疼痛方式等细节
        """

    if field == "其余病史及用药情况":
        prompt += f"""
        特别注意：对于字段"{field}"，请遵循以下规则：
        - 简单询问患者是否有其他疾病
        - 若患者表示没有，无需追问
        """

    if field == "（若有其余病史）请描述具体疾病、治疗方式、用药种类、用法、治疗效果":
        prompt += f"""
        特别注意：对于字段"{field}"，请遵循以下规则：
        - 只需了解大致用药情况，无需精确剂量和详细用法
        - 若患者能提供药物名称和大致用法，即可视为完整回答
        - 无需追问具体治疗效果的详细评估
        """

    prompt += """

    """


    # 调用 API创建医疗随访助手
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
def parse_answer(field, answer, description, history):
    """解析患者回答并提取结构化数据"""
    # 构建提示词
    prompt = f"""
    根据以下对话历史，提取结构化信息：
    {history}
    当前需要提取：{field}
    提取要求："{description}"
    患者最新回答："{answer}"
    请严格按以下JSON格式输出结果：
   {{
     "status": "success|skip|partial_success|ambiguous|pending|escalate",
     "field_value": "提取的值", 
     "confidence": 0-1,
     "reasoning": "决策理由的详细解释,要求简",
     "evidence": "决策的原始对话依据"
   }}
   
    1. 即使患者拒绝回答部分问题，也必须在field_value中保留之前已回答的内容
    2. 当患者明确拒绝回答某个子问题，但已回答其他子问题时，status应设为"partial_success"而非"skip"，
    3. 当一部分子问题已经基本完全回答完，而另一部分子问题患者均无法回答时，status可设为“skip”
    4. 对于多部分问题，即使只回答了一部分，也应将已回答的部分完整提取到field_value中
    5. 单位转换不影响回答完整性，如患者使用不同但等价的单位(如斤/公斤、厘米/米)回答，应视为完整回答，status为"success"
    6. 只要患者提供了问题所需的核心信息，即使格式或单位不同，也应判定为"success"而不是"partial_success"
    7. "field_value"：应专业化，简洁，简短，无需给出建议，因为后续会被填写入excel表中。
    8. 患者即使使用了“大概”，“应该”等类似不确定的词语，也可判定为回答了问题，不用判定为”partial_success“以让患者继续澄清 
   示例：
     - 若问"体重多少公斤"，患者回答"170斤"，应转换为"85公斤"并标记为"success"
     - 若问"身高多少厘米"，患者回答"1米8"，应转换为"180厘米"并标记为"success"
   9. 如有涉及时间问题，当前时间是2025年10月30日
   status说明：
    - success: 患者已经基本回答了全部问题，无需再补充信息
    - partial_success: 患者的当前回答：{answer}，在上一次回答的基础上，或对提问进行了正常的回答，或又进一步回答了部分问题，但当前问题还需要继续提问以补充信息
    - ambiguous: 患者当前回答：{answer}，为空白，或没有回答当前问题，或对问题的回答比较模糊或不符常人认知。
    - skip: 患者不愿或因为忘记而无法提供此信息，
    - pending: 患者明确承诺会上传相关医疗图片或其他数据体检相关数据（如化验单）才可判断为
    - escalate: 不符合上述其他status，需要人工干预的特殊情况
    
    "evidence"要求：
    从对话历史变量`history`中准确提取AI与患者的对话内容，并按照以下格式输出evidence：
    "AI": [AI的发言内容]
    "patient": [患者的发言内容]
    "AI": [AI的发言内容]
    "patient": [患者的发言内容]
    **具体要求：**
    - 保持对话的完整顺序和所有内容，不得对原对话文本删改遗漏
    - 每轮对话都必须分别标注发言者
    - 如果为长对话，确保被被完整提取，但不得提取与问题无关的对话
    **示例：**
    对话历史："AI"：好的，请问您有高血压吗？"patient"：没有。`
    输出："AI": 好的，请问您有高血压吗？
        "patient": 没有。
    
    
    特别规则 - 记忆与嵌套问题处理：
   1. 识别问题之间的依赖关系，区分前置问题和后续问题
   2. 在以下情况下应将status设为"skip"，表示该问题已完成处理：
      a) 患者对前置问题(如"吃过什么药")回答"不记得"、"没有"或"不清楚"，导致后续问题(如"药物剂量")自动失效
      b) 所有子问题都已询问过，且患者明确表示"记不清了"、"想不起来了"等无法提供更多信息
      c) 患者已回答部分子问题，但对剩余子问题明确表示无法回答或记不清
   3. 若问题包含多个独立部分(非嵌套依赖)且部分尚未询问，即使患者对当前部分表示记不清，也应将status设为"partial_success"
   4. 判断依赖关系方法：分析问题内容，识别条件性表述(如"若有"、"如果"、"请描述")
   
   示例：
   - 若问"您吃过什么药？用量是多少？"，患者回答"我没吃过药"或"不记得吃过什么药"，应标记为"skip"
   - 若问"您的症状有哪些？持续多久？"，患者回答"有头痛，其他症状和持续时间记不清了"，且这些问题都已询问过，应标记为"skip"
   - 若问"您有哪些慢性病？"包含多个独立部分(高血压、糖尿病等)，但只询问了部分，患者回答"高血压记不清了"，应标记为"partial_success"继续询问其他疾病
     
     JSON格式输出具体要求：
    1. field_value 应是文本提取结果，为字符串格式
    2. confidence 是置信度评分(0.0-1.0)，是浮点数
    3. reasoning 是解释,用于简短说明如何提取出答案，是字符串格式
    4. 不要包含任何额外文本或解释
    5. 确保是有效的JSON格式
    """

    standardized_fields = [
        "当前有无糖尿病",
        "当前有无高血压",
        "是否曾患冠心病",
        "是否曾患脑血管病",
        "近一年是否存在手术切口疼痛"
    ]
    if field in standardized_fields:
        prompt += f"""
        特别注意：对于字段"{field}"，请严格按以下规则标准化输出：
        - 如果患者表示肯定、有、存在、患有该情况的任何表述，field_value必须输出：是
        - 如果患者表示否定、没有、无、不存在该情况的任何表述，field_value必须输出：否
        - 如果信息不明确、模糊或无法确定，field_value必须输出：未知
        - field_value只能是"是"、"否"、"未知"三个值之一，不接受其他任何表述
        """

    if field == "当前身高":
        prompt += f"""
        特别注意：对于此字段，请遵循以下规则：
        - 只需提取到大致即可，例：若患者回答为170多，则记录为170cm即可，并判定为success
        - 提取的值的单位应为cm
        """
    if field == "当前体重":
        prompt += f"""
        特别注意：对于此字段，请遵循以下规则：
        - 只需提取到大致即可，例：若患者回答为一百五十多斤，则看作为75kg即可，并判定为success
        - 单位应记录应为kg
        """
    if field == "（若曾患脑血管病）具体疾病、治疗方式及有无后遗症":
        prompt += f"""
        特别注意：对于此字段，请遵循以下规则：
        - 只需提取到疾病类型、大致治疗方式和后遗症有无即可判定为success
        - 无需过于详细的治疗方式的治疗细节，了解大致方法(药物/手术/介入)即可
        """
    if field == "（若有糖尿病）药物控制方案":
        prompt += f"""
        特别注意：对于此字段，请遵循以下规则：
        - 无需过于详细的治疗方式的治疗细节，了解大致方法即可
        - 对于空腹血糖，只需了解大致即可
        """
    if field == "近一年是否存在手术切口疼痛":
        prompt += f"""
        特别注意：对于此字段"{field}"，请遵循以下规则：
        - 只需确认患者在近一年内是否有手术史及切口是否疼痛即可
        - 患者只需要提供大致时间，即可判定为success
        """
    if field == "其余病史及用药情况":
        prompt += f"""
        注意：对于字段"{field}"，请按照以下规则输出：
        - 如果患者有其余病史，field_value应提取到具体的疾病才可判定为success；若患者没有其余病史， field_value必须输出：否
        - 如果信息不明确、模糊或无法确定，field_value必须输出：未知
        """
    if field == "（若有其余病史）请描述具体疾病、治疗方式、用药种类、用法、治疗效果":
        prompt += f"""
        特别注意：对于字段"{field}"，请按照以下规则输出：
        - 对于用药情况的描述，了解大致内容(“药物名称、用药时间、用药剂量“)即可
        - field_value可以包含多个药物的描述（如果适用），用逗号分隔。
        """
    if field == "（若存在手术切口疼痛）手术切口疼痛持续时间":
        prompt += f"""
        注意：对于此字段，请按照以下规则输出：
        -疼痛持续时间不要求具体到时间单位，如：提取结果为：术后至今，间断出现等等。也均可判定为success
        """
    if field == "随访时受者状态":
        prompt += f"""
        注意：对于此字段，请按照以下规则输出：
        - 只需提取到大致即可，例：若患者回答为170多，则记录为170umol/L即可，并判定为success
        """

    # 调用 API创建医疗数据解析助手
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
        clean_result = re.sub(r'^```json\n|\n```$', '', raw_result).strip()
        re_result = json.loads(clean_result)
        print(f"解析结果：{re_result['field_value']}  置信度：{re_result['confidence']}  解释：{re_result['reasoning']}")
        return re_result
    except (json.JSONDecodeError, KeyError) as e:
        print(f"解析答案出错: {e}")
        return {"field_value": "", "confidence": 0.0}
    except Exception as e:
        print(f"API调用出错: {e}")
        return {"field_value": "", "confidence": 0.0}




'''
try：
completion.choices[0].message.content,模型返回的是'```json\n{"field_value": "175cm", "confidence": 1.0}\n```'的式的内容，
但是json.loads()括号中输入的内容希望是以“{”开头，并且以“}”结尾的，如果直接将值送到json.loads，就会出现下面json.JSONDecodeError式的错误。
因此我们采用re.sub(r'^```json\n|\n```$', '', raw_result).strip()删除开头与结尾的'```json\n这些东西然后再送到json.loads()中

json.loads(...)  核心函数：将JSON格式的字符串转换为Python数据结构，在这里是将字符串转变为字典类型，这样后面才能用result['field_value']去调用值，

(json.JSONDecodeError, KeyError) as e:的意思是捕获圆括号中的这组异常中的任意一种并赋值给e
json.JSONDecodeError含义：当 json.loads() 尝试解析无效 JSON 字符串时会出现的异常，
这种异常一般是因为字符串不是有效的 JSON 格式或者模型返回了非 JSON 内容（如自然语言解释）
KeyError含义：当尝试访问字典中不存在的键时出现的异常
这种异常一般是因为模型返回了 JSON 的内容，但并没有按照 {{"field_value": "提取的值", "confidence": 0-1}}的要求去返回
'''
