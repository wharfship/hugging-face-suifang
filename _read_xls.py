import pandas as pd

df = pd.read_excel('2025.5.28人工智能供者随访计划excel版.xls', sheet_name='Sheet1')
print('列名:', df.columns.tolist())
print('总行数:', len(df))
print()
for i, row in df.iterrows():
    col0 = row.iloc[0]
    col1 = row.iloc[1] if len(row) > 1 else ''
    col2 = row.iloc[2] if len(row) > 2 else ''
    print(f'行{i} | 填写内容: {col0} | 字段含义: {col1} | 示例: {col2}')
