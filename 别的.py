prompt = "根据以下对话历史，提取结构化信息"

print(prompt)

# 使用 += 添加内容
prompt += """
特别注意：对于特定字段，请按以下规则处理：
- 规则1
- 规则2
"""

# 最终结果
print(prompt)