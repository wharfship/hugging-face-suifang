"""
with gr.Blocks() as demo => 创建空白页面

文本框 => gr.Textbox()
    属性 =>
        label = ""  =>文本框的标题
        placeholder =>文本框的提示信息
按钮 => gr.Button  创建一个按钮，可以用于绑定点击事件

滑块 => gr.slider  创建一个滑块
    属性 =>
        minimun => 最小值
        maxinum => 最大值
        value => 默认值
        label => 选择数值

下拉框 => gr.Dropdown 创建一个下拉框
    属性 =>
        choices =>选择项  注意是choices不是choice
        label =>标题

文件上传 => gr.File 进行文件上传
    属性 =>
        file_types => 允许上传的文件类型  “注意file_types是复数”

聊天界面 => gr.Chat 创建一个聊天界面用于和聊天机器人进行交互
    属性 =>
        label => 标题

布局 => with gr.Row():  创建一行
       with gr.Column():  创建一列
    属性 =>
    scale => 用于设置比例

"""
import gradio as gr

#创建空白界面
with gr.Blocks() as demo:
    #创建输入框textbox
    textbox = gr.Textbox(label="<这是一个输入框>",placeholder="请输入文本")

    #创建按钮命名为：”提交“
    gr.Button("提交")

    #创建滑块
    slider = gr.Slider(label="<这是一个滑块>",minimum=0,maximum=100,value=50)

    #创建一个下拉框
    dropdown = gr.Dropdown(label="<这是一个下拉框>",choices=["选项1","选项2","选项3草泥马"])

    #创建一个文件上传
    upload_file = gr.File(label="<这是用来上传文件的>",file_types=["pdf","png","jpg","jpeg","txt"])

    #创建一个聊天界面
    #chatbot = gr.Chatbot(label="客服聊天机器大人")

    #创建布局
    with gr.Row(scale=8):
        with gr.Column(scale=3):
            textbox = gr.Textbox(label="<这是一个输入框>", placeholder="请输入文本1")
        with gr.Column(scale=4):
            slider = gr.Slider(label="<这是一个滑块>",minimum=0,maximum=100,value=50)
        with gr.Column(scale=5):
            gr.Button("提交")
    with gr.Row(scale=2):
        upload_file = gr.File(label="<这是用来上传文件的>", file_types=["pdf", "png", "jpg", "jpeg", "txt"])
if __name__=='__main__':
    demo.launch()
