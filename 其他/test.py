import gradio as gr
import pandas as pd
import os
import shutil
import tempfile


def process_and_preview_xls(file_obj):
    if file_obj is None:
        return None, None

    # 1. 处理文件下载：将文件保存到一个指定目录并返回路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(current_dir, "output_files")
    os.makedirs(output_dir, exist_ok=True)

    file_name = file_obj.orig_name
    output_path = os.path.join(output_dir, file_name)
    shutil.copy(file_obj.name, output_path)

    # 2. 处理预览：尝试用pandas读取xls文件
    try:
        # 注意：需要安装 xlrd 或 openpyxl 库来读取.xls文件
        # pip install xlrd
        df = pd.read_excel(file_obj.name)
        preview_df = df.head(10)  # 只预览前10行，避免数据过多
    except Exception as e:
        print(f"读取Excel文件时出错: {e}")
        preview_df = pd.DataFrame({"Error": [f"无法读取文件: {str(e)}"]})

    return output_path, preview_df


with gr.Blocks() as demo:
    gr.Markdown("# XLS 文件查看与下载")

    with gr.Row():
        with gr.Column():
            file_input = gr.File(label="请上传一个.xls文件", file_types=['.xls'])
            submit_btn = gr.Button("生成预览和下载链接")
        with gr.Column():
            download_output = gr.File(label="文件下载")
            data_preview = gr.Dataframe(label="数据预览 (前10行)", interactive=False)

    submit_btn.click(
        fn=process_and_preview_xls,
        inputs=file_input,
        outputs=[download_output, data_preview]
    )

demo.launch()