"""Attachment context tool adapter."""

from agent.contracts import AgentTurnContext


def build_attachment_context_tool(context: AgentTurnContext):
    """Create a per-turn attachment context reader tool."""

    def read_attachment_context() -> str:
        """Return available parsed attachment context for this turn."""

        if not context.attachment_public_ids:
            return "本轮没有附件。"

        if not context.attachment_context:
            return (
                "本轮包含附件，但附件解析上下文尚未接入 Agent 工具。"
                f" 附件 ID: {', '.join(context.attachment_public_ids)}。"
            )

        rendered_items: list[str] = []
        for item in context.attachment_context:
            title = item.get("title") or item.get("file_name") or "未知附件"
            content = str(item.get("content") or item.get("raw_text") or "").strip()
            if content:
                rendered_items.append(f"[附件: {title}]\n{content}")

        return "\n\n".join(rendered_items) if rendered_items else "附件暂无可用文本内容。"

    return read_attachment_context
