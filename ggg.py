from Model_initialization import *
import gradio as gr
import tempfile
import os
import time
from datetime import datetime
from excel_adjusting import *


excel_path = '2025.5.28人工智能供者随访计划excel版.xls'
metadata = load_excel_template(excel_path)
tracker = FieldStateTracker(metadata)
field_attempts = {}
chat_history = []   #专门给gradio的Chatbot用的


def init_system():
    """初始化系统,恢复到初始数据"""
    global tracker, metadata
    metadata = load_excel_template(excel_path)
    tracker = FieldStateTracker(metadata)
    field_attempts.clear()
    chat_history.clear()

    column_names = {
        "field": "填写内容",
        "value": "填写数据",
        "evidence": "数据原始依据",
        "status": "读取情况"
    }
    df = pd.DataFrame(tracker.get_parse_history())
    # 重命名
    df = df.rename(columns=column_names)
    # 导出为Excel文件(该步并没有改变df内容与格式，他仍旧是pandas.dataframe类的形式
    excel_file = "医疗数据.xlsx"
    df.to_excel(excel_file, index=False, engine="openpyxl")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "医疗数据.xlsx")
    # 调整excel表的格式
    format_excel(file_path, "医疗数据.xlsx")

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
    return "初始化系统成功", chat_history, field, file_path, pd.DataFrame()


def process_user_input(user_message, chat_history):
    """处理用户输入"""
    global tracker, field_attempts
    # 添加用户消息到历史
    tracker.add_dialogue("Patient", user_message)
    chat_history.append({"role": "user", "content": user_message})
    # 获取当前字段的内容
    field = tracker.get_next_field()
    # 获取对话历史文本
    history_text = tracker.get_dialogue_history()
    # 解析用户回答
    start_parse = time.time()
    result = parse_answer(field, user_message, metadata[field]['描述'], history_text)
    end_parse = time.time()
    print(f"🔍 解析 parse_answer() 耗时：{end_parse - start_parse:.2f} 秒")
    print(f"AI提取的数据原始依据:{result['evidence']}")
    parse_output = f"解析状态:{result['status']},  置信度：{result['confidence']}\n解释：{result['reasoning']}"

    # 处理解析结果,并保存数据
    if result["status"] == "success":
        tracker.update_field(field, result)
        confirmation = f"已记录: {field} = {result['field_value']} (置信度: {result['confidence']:.2f})"
        tracker.add_dialogue("AI", confirmation)
        chat_history.append({"role": "assistant", "content": confirmation})

    elif result["status"] == "ambiguous":
        # 无效提问次数加一
        field_attempts[field] = field_attempts.get(field, 0) + 1
        if field_attempts[field] >= 3:
            result["status"] = "escalate"
            tracker.update_field(field, result)
            confirmation = "我们暂时跳过这个问题,后续将进行人工介入处理。"
            tracker.add_dialogue("AI", confirmation)
            chat_history.append({"role": "assistant", "content": confirmation})

    elif result["status"] == "skip":
        tracker.update_field(field, result)
        confirmation = "好的"
        tracker.add_dialogue("AI", confirmation)
        chat_history.append({"role": "assistant", "content": confirmation})

    elif result["status"] == "pending":
        tracker.update_field(field, result)
        confirmation = "好的"
        tracker.add_dialogue("AI", confirmation)
        chat_history.append({"role": "assistant", "content": confirmation})

    elif result["status"] == "escalate":
        tracker.update_field(field, result)
        confirmation = "我们暂时跳过这个问题,后续将进行人工介入处理。"
        tracker.add_dialogue("AI", confirmation)
        chat_history.append({"role": "assistant", "content": confirmation})


    """将filled_data字典转为excel形式并保存，命名为医疗数据.xlsx，并进行格式调整"""
    # 重命名列标题（可选，如果希望Excel表头显示中文）
    column_names = {
        "field": "填写内容",
        "value": "填写数据",
        "evidence": "数据原始依据",
        "status": "读取情况"
    }
    # 获取解析文本历史（就是填写好的数据），并转为pandas.DataFrame类的形式
    df = pd.DataFrame(tracker.get_parse_history())
    # 重命名
    df = df.rename(columns=column_names)
    # 导出为Excel文件(该步并没有改变df内容与格式，他仍旧是pandas.dataframe类的形式
    excel_file = "医疗数据.xlsx"
    df.to_excel(excel_file, index=False, engine="openpyxl")
    # 获取excel表的绝对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "医疗数据.xlsx")
    # 调整excel表的格式
    format_excel(file_path, "医疗数据.xlsx")


    # 获取下一个问题
    field = tracker.get_next_field()

    """对特殊的字段进行专门处理"""
    if field == "BMI":
        if tracker.get_field_status('当前身高') == "success" and tracker.get_field_status('当前体重') == "success":
            result = parse_answer(field, '', metadata, history_text)
            tracker.update_field(field, result, '由体重和身高自动计算生成')
            confirmation = f"已记录: {field} = {result['field_value']} (置信度: {result['confidence']:.2f})"
            tracker.add_dialogue("AI", confirmation)
            chat_history.append({"role": "assistant", "content": confirmation})

            """将parse_histiory存为excel形式"""
            column_names = {
                "field": "填写内容",
                "value": "填写数据",
                "evidence": "数据原始依据",
                "status": "读取情况"
            }
            df = pd.DataFrame(tracker.get_parse_history())
            df = df.rename(columns=column_names)
            excel_file = "医疗数据.xlsx"
            df.to_excel(excel_file, index=False, engine="openpyxl")
            script_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(script_dir, "医疗数据.xlsx")
            format_excel(file_path, "医疗数据.xlsx")
            field = tracker.get_next_field()
        else :
            result = parse_answer(field, '', metadata, history_text)
            tracker.update_field(field, result, '无法计算')
            field = tracker.get_next_field()


    if field is None:
        completion_msg = "所有信息已收集完成，请您点击左上角“导出并下载”按钮进行下载！"
        tracker.add_dialogue("AI", completion_msg)
        chat_history.append({"role": "assistant", "content": completion_msg})
        # 获取excel表的绝对路径
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, "医疗数据.xlsx")
        format_excel(file_path, "医疗数据.xlsx")
        return "", chat_history, field, parse_output, file_path, df


    """对问题提问"""
    history_text = tracker.get_dialogue_history()
    start_parse = time.time()
    question = generate_question(field, metadata, history_text, tracker.get_field_status(field))
    end_parse = time.time()
    print(f"🔍 生成问题 generate_question() 耗时：{end_parse - start_parse:.2f} 秒")
    tracker.add_dialogue("AI", question)
    chat_history.append({"role": "assistant", "content": question})
    return "", chat_history, field, parse_output, file_path, df



def download_data():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "医疗数据.xlsx")
    if not os.path.exists(file_path):
        print(f"警告: 文件 {file_path} 不存在!")
        # 在实际应用中，你可能需要处理文件不存在的情况
    return file_path

def on_edit(edited_df):
    """dataframe数据编辑后，进行保存"""
    global tracker
    """每次单元格编辑完成就触发：同步回全局 df"""
    df = pd.DataFrame(tracker.get_parse_history())
    df = edited_df.copy()        # 覆盖原始 df（安全做法）
    excel_file = "医疗数据.xlsx"
    df.to_excel(excel_file, index=False, engine="openpyxl")
    # 获取excel表的绝对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "医疗数据.xlsx")
    #调整excel表格格式
    format_excel(file_path, "医疗数据.xlsx")
    return gr.update(value="✅ 已自动保存（内存）"), file_path


# 创建Gradio界面
with gr.Blocks(title="AI医疗随访系统") as demo:
    gr.Markdown("# AI医疗随访对话系统")
    gr.Markdown("AI对话系统")

    with gr.Row():
        with gr.Column(scale=1):
            init_btn = gr.Button("初始化系统", variant="primary")
            download_btn = gr.DownloadButton(label="导出并下载", value=download_data, visible=True)
            status_output = gr.Textbox(label="系统状态")
            parse_output = gr.Textbox(label="上一问题解析情况",lines=2)
            question_output = gr.Textbox(label="当前要回答的问题")
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(label="对话记录", height=500, layout="bubble")
            msg = gr.Textbox(
                label="请输入您的回答",
                placeholder="在这里输入您的回答...",
                lines=1
            )
            submit_btn = gr.Button("发送", variant="primary")
    dataframe_output = gr.Dataframe(label="文件内容", interactive=True)

    # 绑定事件处理
    init_btn.click(fn=init_system, outputs=[status_output, chatbot, question_output, download_btn, dataframe_output])
    demo.load(fn=init_system, outputs=[status_output, chatbot, question_output, download_btn, dataframe_output])  # 系统开始会自动点一下初始化按钮
    download_btn.click(fn=download_data, outputs=download_btn)
    dataframe_output.edit(fn=on_edit, inputs=dataframe_output, outputs=[status_output, download_btn])

    def respond(message, chat_history):
        # 处理用户输入
        _, updated_chat_history, question_output, parse_output, file_path, df = process_user_input(message, chat_history)
        return "", updated_chat_history, question_output, parse_output, file_path, df


    msg.submit(fn=respond, inputs=[msg, chatbot], outputs=[msg, chatbot, question_output, parse_output, download_btn, dataframe_output])
    submit_btn.click(fn=respond, inputs=[msg, chatbot], outputs=[msg, chatbot, question_output, parse_output, download_btn, dataframe_output])


# 保留原有的main_flow函数，但不再直接调用
def main_flow(excel_path):
    """原有的主流程函数，现在通过Gradio界面调用"""
    # 这个函数现在通过Gradio界面调用，不再直接运行
    pass


if __name__ == "__main__":
    # 启动Gradio界面
    demo.launch()
