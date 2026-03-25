from Model_initialization import *
import gradio as gr
import tempfile
import os
import time
from datetime import datetime

excel_path = '../simple.xls'
metadata = load_excel_template(excel_path)
tracker = FieldStateTracker(metadata)
field_attempts = {}
chat_history = []


def init_system():
    """初始化系统,恢复到初始数据"""
    global tracker, metadata
    metadata = load_excel_template(excel_path)
    tracker = FieldStateTracker(metadata)
    field_attempts.clear()
    chat_history.clear()
    # 添加初始问候语
    greeting = "您好，我是医疗随访助手，需要了解您的健康状况。"
    tracker.add_dialogue("AI", greeting)
    chat_history.append({"role": "assistant", "content": greeting})
    # 产生第一个问题
    field = tracker.get_next_field()
    history_text = tracker.get_dialogue_history()
    question = generate_question(field, metadata, history_text)
    tracker.add_dialogue("AI", question)
    chat_history.append({"role": "assistant", "content": question})
    return "初始化系统成功", chat_history, field


def process_user_input(user_message, chat_history):
    """处理用户输入"""
    global tracker, field_attempts
    # 添加用户消息到历史
    tracker.add_dialogue("Patient", user_message)
    chat_history.append({"role": "user", "content": user_message})

    # 获取下一个需要提问的字段
    field = tracker.get_next_field()

    if field is None:
        completion_msg = "所有信息已收集完成，感谢您的配合！"
        tracker.add_dialogue("AI", completion_msg)
        chat_history.append({"role": "assistant", "content": completion_msg})
        return "", chat_history

    # 更新尝试次数
    field_attempts[field] = field_attempts.get(field, 0) + 1

    # 检查是否超过最大尝试次数
    if field_attempts[field] > 3:
        skip_msg = f"已多次询问{field}，将跳过此问题"
        tracker.add_dialogue("AI", skip_msg)
        chat_history.append({"role": "AI", "content": skip_msg})
        return "", chat_history

    # 获取对话历史文本
    history_text = tracker.get_dialogue_history()

    # 解析用户回答
    result = parse_answer(field, user_message, metadata, history_text)
    parse_output = f"解析状态:{result['status']},  置信度：{result['confidence']}\n解释：{result['reasoning']}"

    # 处理解析结果
    if result["status"] == "success":
        tracker.update_field(field, result, user_message)
        confirmation = f"已记录: {field} = {result['field_value']} (置信度: {result['confidence']:.2f})"
        tracker.add_dialogue("AI", confirmation)
        chat_history.append({"role": "assistant", "content": confirmation})

    elif result["status"] == "skip":
        tracker.update_field(field, result, user_message)
        confirmation = "了解，我们跳过这个问题"
        tracker.add_dialogue("AI", confirmation)
        chat_history.append({"role": "assistant", "content": confirmation})

    elif result["status"] == "retry":
        if field_attempts[field] >= 2:
            tracker.update_field(field, result, user_message)
            confirmation = "我们暂时跳过这个问题,后续转接专业人员给您进一步了解。"
            tracker.add_dialogue("AI", confirmation)
            chat_history.append({"role": "assistant", "content": confirmation})

    elif result["status"] == "pending":
        tracker.update_field(field, result, user_message)
        confirmation = "好的，请您后续尽快上传检查报告单等相关文件，我们进行下一个问题"
        tracker.add_dialogue("AI", confirmation)
        chat_history.append({"role": "assistant", "content": confirmation})

    elif result["status"] == "escalate":
        tracker.update_field(field, result, user_message)
        confirmation = "后续该问题我们将进行人工介入"
        tracker.add_dialogue("AI", confirmation)
        chat_history.append({"role": "assistant", "content": confirmation})

    # 获取下一个问题
    field = tracker.get_next_field()
    if field is None:
        completion_msg = "所有信息已收集完成，请您点击导出数据按钮，然后进行下载！"
        tracker.add_dialogue("AI", completion_msg)
        chat_history.append({"role": "assistant", "content": completion_msg})
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
        return "", chat_history, field, parse_output

    # 生成下一个问题
    history_text = tracker.get_dialogue_history()
    question = generate_question(field, metadata, history_text)
    tracker.add_dialogue("AI", question)
    chat_history.append({"role": "assistant", "content": question})

    return "", chat_history, field, parse_output


def export_data():
    """导出数据为Excel"""
    if tracker is None:
        return "请先进行对话收集数据"

    df = pd.DataFrame(tracker.get_parse_history())
    column_names = {
        "field": "填写内容",
        "value": "填写数据",
        "evidence": "数据原始依据"
    }
    df = df.rename(columns=column_names)

    # 导出为Excel文件
    excel_file = "../医疗数据.xlsx"
    df.to_excel(excel_file, index=False, engine="openpyxl")
    # 获得文件路径去返回
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "医疗数据.xlsx")
    return f"数据已成功导出到: {excel_file}", file_path


def download_data():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "医疗数据.xlsx")
    if not os.path.exists(file_path):
        print(f"警告: 文件 {file_path} 不存在!")
        # 在实际应用中，你可能需要处理文件不存在的情况
    return file_path


# 创建Gradio界面
with gr.Blocks(title="AI医疗随访系统") as demo:
    gr.Markdown("# AI医疗随访对话系统")
    gr.Markdown("AI对话系统")

    with gr.Row():
        with gr.Column(scale=1):
            init_btn = gr.Button("初始化系统", variant="primary")
            export_btn = gr.Button("导出数据")
            download_btn = gr.DownloadButton(label="下载", value=download_data, visible=True)
            status_output = gr.Textbox(label="系统状态")
            parse_output = gr.Textbox(label="上一问题解析情况")
            question_output = gr.Textbox(label="当前要回答的问题")
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(label="对话记录", height=500, layout="bubble", type='messages')
            msg = gr.Textbox(
                label="请输入您的回答",
                placeholder="在这里输入您的回答...",
                lines=1
            )
            submit_btn = gr.Button("发送", variant="primary")

    # 绑定事件处理
    init_btn.click(fn=init_system, outputs=[status_output, chatbot, question_output])
    export_btn.click(fn=export_data, outputs=[status_output, download_btn])
    demo.load(fn=init_system, outputs=[status_output, chatbot, question_output])  # 系统开始会自动点一下初始化按钮
    download_btn.click(fn=download_data, outputs=download_btn)


    def respond(message, chat_history):
        # 处理用户输入
        _, updated_chat_history, question_output, parse_output = process_user_input(message, chat_history)
        _, file_path = export_data()
        return "", updated_chat_history, question_output, parse_output, file_path


    msg.submit(fn=respond, inputs=[msg, chatbot], outputs=[msg, chatbot, question_output, parse_output, download_btn])
    submit_btn.click(fn=respond, inputs=[msg, chatbot], outputs=[msg, chatbot, question_output, parse_output, download_btn])


# 保留原有的main_flow函数，但不再直接调用
def main_flow(excel_path):
    """原有的主流程函数，现在通过Gradio界面调用"""
    # 这个函数现在通过Gradio界面调用，不再直接运行
    pass


if __name__ == "__main__":
    # 启动Gradio界面
    demo.launch()
