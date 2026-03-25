import gradio as gr
import pandas as pd
import tempfile
import os


def process_excel_file(file_obj):
    """
    处理上传的Excel文件，返回DataFrame内容和供下载的文件路径
    """
    # 读取上传的Excel文件
    df = pd.read_excel(file_obj.name)
    print(type(df));
    # 为了提供下载，我们通常需要将处理后的数据保存到一个临时文件
    # 这里我们简单地保存为一个新的Excel文件（在实际应用中，你可能会对数据进行处理）
    temp_dir = tempfile.mkdtemp()
    output_filename = os.path.join(temp_dir, "processed_file.xlsx")
    df.to_excel(output_filename, index=False)

    # 返回两部分：DataFrame内容（用于展示）和文件路径（用于下载）
    return df, output_filename



# 定义Gradio界面
with gr.Blocks(title="Excel文件查看与下载器") as demo:
    gr.Markdown("# 📊 Excel文件查看与下载器")
    gr.Markdown("上传一个.xls或.xlsx文件，你可以查看其内容并下载处理后的版本。")

    with gr.Row():
        file_input = gr.File(label="上传Excel文件", file_types=[".xls", ".xlsx"])
        submit_btn = gr.Button("处理文件")

    with gr.Row():
        # 用于展示DataFrame内容
        dataframe_output = gr.Dataframe(label="文件内容", interactive=False)
        # 下载按钮组件
        download_output = gr.DownloadButton(label="下载处理后的文件", visible=False
                    )


    # 处理按钮点击事件
    def handle_file(file_obj):
        if file_obj is None:
            return None, None
        df, file_path = process_excel_file(file_obj)
        # 返回DataFrame内容，并让下载按钮可见并提供文件路径
        return df, file_path


    submit_btn.click(
        fn=handle_file,
        inputs=file_input,
        outputs=[dataframe_output, download_output]
    )

    # 当文件上传后，自动触发处理（可选）
    file_input.upload(
        fn=handle_file,
        inputs=file_input,
        outputs=[dataframe_output, download_output]
    )

# 启动应用
if __name__ == "__main__":
    demo.launch()