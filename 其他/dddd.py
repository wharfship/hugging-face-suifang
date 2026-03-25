import gradio as gr
import os

# 假设你的"医疗数据.xls"文件位于当前目录下
script_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(script_dir, "医疗数据.xlsx")
print(file_path)
# 检查文件是否存在
if not os.path.exists(file_path):
    print(f"警告: 文件 {file_path} 不存在!")
    # 在实际应用中，你可能需要处理文件不存在的情况

# 创建Gradio界面
with gr.Blocks(title="医疗数据下载") as demo:
    gr.Markdown("# 医疗数据下载")
    gr.Markdown("点击下方按钮下载医疗数据表格")

    # 直接提供下载按钮，指向已有的文件
    gr.DownloadButton(label="下载医疗数据表格",value=file_path,  visible=True)

# 启动应用
demo.launch()