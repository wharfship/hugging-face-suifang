from Model_initialization import *
import pandas as pd


def main_flow(excel_path):
    """主流程函数"""
    # 初始化组件
    metadata = load_excel_template(excel_path)
    tracker = FieldStateTracker(metadata)
    field_attempts = {}#(询问次数)
    # 问候语
    tracker.add_dialogue("AI", "您好，我是医疗随访助手，需要了解您的健康状况。")
    print("AI: 您好，我是医疗随访助手，需要了解您的健康状况。")

    # 对话循环
    while True:
        field = tracker.get_next_field()
        if field is None:
            print("AI: 所有信息已收集完成，感谢您的配合！")
            break
        field_attempts[field] = field_attempts.get(field, 0) + 1
        # 检查是否超过最大尝试次数
        if field_attempts[field] > 3:
            print(f"AI: 已多次询问{field}，将跳过此问题")
            tracker.mark_field_skipped(field, "超过最大尝试次数")
            continue
        # 获取对话历史文本
        history_text = tracker.get_dialogue_history()   #读取dialogue_history列表中AI和patient之前的所有对话记录
        # AI生成问题
        question = generate_question(field, metadata, history_text) #开始对话，由ai发起
        tracker.add_dialogue("AI", question)   #将AI说的话存在类tracker的dialogue_history列表中
        print(f"AI: {question}")
        print("当前字段位置：", field)
        # 用户回答问题
        answer = input("Patient: ")
        tracker.add_dialogue("Patient", answer) #将患者patient说的话存在类tracker的dialogue_history列表中
        # 解析助手解析结果以及其他数据
        result = parse_answer(field, answer, metadata, history_text)#当前字段名field，患者的回答内容answer，整个数据集：metadata，对话记录history_text
        print(f"提取状态为：{result['status']}")
        # 处理解析结果
        if result["status"] == "success":
            # 成功提取信息
            tracker.update_field(field, result['field_value'], answer)
            print(f"AI: 已记录: {field} = {result['field_value']} (置信度: {result['confidence']:.2f})")
        elif result["status"] == "skip":
            # 跳过此字段
            tracker.update_field(field, result['field_value'], answer)
            tracker.mark_field_skipped(field, result.get("reason", "患者无法提供"))
            print("AI:了解，我们跳过这个问题")
        elif result["status"] == "retry":
            if field_attempts[field] >= 2:
                tracker.update_field(field, result['field_value'], answer)
                print("AI: 我们暂时跳过这个问题,后续转接专业人员给您进一步了解。")
        elif result["status"] == "pending":
            tracker.update_field(field, result['field_value'], answer)
            print("AI:好的，请您后续尽快上传检查报告单等相关文件，我们进行下一个问题")
        elif result["status"] == "escalate":
            tracker.update_field(field, result['field_value'], answer)
            print("AI: 后续该问题我们将进行人工介入")

        # if result['confidence'] > 0.6:
        #     tracker.update_field(field, result['field_value'], answer)
        #     print(f"AI: 已记录: {field} = {result['field_value']}")



    df = pd.DataFrame(tracker.get_parse_history())
    # 重命名列标题（可选，如果希望Excel表头显示中文）
    column_names = {
        "field": "填写内容",
        "value": "填写数据",
        "evidence": "数据原始依据"
    }
    df = df.rename(columns=column_names)
    # 导出为Excel文件
    excel_file = "../医疗数据.xlsx"
    df.to_excel(excel_file, index=False, engine="openpyxl")
    print(f"数据已成功导出到: {excel_file}")


if __name__ == "__main__":
    main_flow('../2025.5.28人工智能供者随访计划excel版.xls')

