import openpyxl
from openpyxl.styles import Font
import os

def format_excel(file_path, save_path=None):
    if save_path is None:
        save_path = file_path

    # 打开工作簿
    wb = openpyxl.load_workbook(file_path)

    # 遍历所有工作表
    for ws in wb.worksheets:
        # 设置前四列宽度（以字符为单位）
        ws.column_dimensions['A'].width = 45
        ws.column_dimensions['B'].width = 30
        ws.column_dimensions['C'].width = 50

        # 遍历所有单元格设置字体
        for row in ws.iter_rows():
            for cell in row:
                if cell.value:
                    # 检查单元格内容是否包含中文字符
                    has_chinese = any('\u4e00' <= char <= '\u9fff' for char in str(cell.value))

                    if has_chinese:
                        # 如果包含中文，设置为微软雅黑
                        cell.font = Font(name='微软雅黑')
                    else:
                        # 如果不包含中文，设置为Times New Roman
                        cell.font = Font(name='Times New Roman')

    # 保存工作簿
    wb.save(save_path)
    return True

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "medical_data.xlsx")
    if os.path.exists(file_path):
        format_excel(file_path, file_path)
