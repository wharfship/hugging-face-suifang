class FieldStateTracker:
    def __init__(self, template_data):
        self.template = template_data
        self.filled_data = {}
        self.pending_fields = list(template_data.keys())
        self.dialogue_history = []
        self.parse_history = []

    def get_next_field(self):
        """获取下一个需要提问的字段"""
        for field in self.pending_fields:
            dependencies = self.template[field]["依赖"]
            if not dependencies:
                return field

            parent = dependencies["parent"]
            if parent not in self.filled_data:
                continue

            parent_value = self.filled_data[parent]["value"]
            condition = dependencies.get("condition")
            opposite_condition = dependencies.get("opposite_condition")

            if condition is not None:
                allowed_values = condition if isinstance(condition, list) else [condition]
                if parent_value in allowed_values:
                    return field
            elif opposite_condition is not None:
                blocked_values = opposite_condition if isinstance(opposite_condition, list) else [opposite_condition]
                if parent_value not in blocked_values:
                    return field

        return None

    def update_field(self, field, result, evidence=None):
        """更新字段状态"""
        evidence_text = evidence if evidence is not None else result.get("evidence", "")
        completion = result.get("completion", "")
        reasoning = result.get("reasoning", "")

        self.filled_data[field] = {
            "value": result.get("field_value", ""),
            "evidence": evidence_text,
            "status": result.get("status", ""),
            "completion": completion,
            "reasoning": reasoning,
        }

        if field in self.pending_fields:
            self.pending_fields.remove(field)

        self.parse_history.append({
            "field": field,
            "value": result.get("field_value", ""),
            "evidence": evidence_text,
            "status": result.get("status", ""),
            "completion": completion,
            "reasoning": reasoning,
        })

    def add_dialogue(self, role, content):
        """添加对话记录"""
        self.dialogue_history.append({
            "role": role,
            "content": content,
        })

    def get_field_value(self, field):
        if field in self.filled_data:
            return self.filled_data[field]["value"]
        return None

    def get_field_status(self, field):
        if field in self.filled_data:
            return self.filled_data[field]["status"]
        return None

    def get_field_completion(self, field):
        if field in self.filled_data:
            return self.filled_data[field].get("completion")
        return None

    def get_conversation_text(self):
        conversation = []
        for entry in self.dialogue_history:
            prefix = "AI: " if entry["role"] == "AI" else "Patient: "
            conversation.append(f"{prefix}{entry['content']}")
        return "\n".join(conversation)

    def get_dialogue_history(self):
        return self.dialogue_history

    def get_parse_history(self):
        return self.parse_history
