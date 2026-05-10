"""System prompt construction for CookingAgent."""

from agent.contracts import AgentTurnContext, RagContext, WebSearchContext
from agent.prompts.rag_prompts import render_retrieved_chunks


def build_system_prompt(context: AgentTurnContext) -> str:
    """Build the system prompt for one agent turn."""

    return "\n".join(
        [
            "你是 CookingAgent，一个面向做菜、食材、菜谱、营养和厨房流程的中文智能助手。",
            "回答要直接、清晰、可执行。涉及步骤时优先使用分点或编号。",
            "不要编造不存在的文件、知识库来源、联网搜索结果或网页链接。",
            _build_rag_instruction(context.rag_context),
            _build_web_search_instruction(context.web_search_context),
            _build_attachment_instruction(context),
            "生成菜谱时要覆盖食材、调味、步骤、时间、火候和可替换方案。",
        ]
    )


def _build_rag_instruction(rag_context: RagContext | None) -> str:
    if rag_context is None or not rag_context.enabled:
        return (
            "本轮没有可用的后端默认知识库上下文。可以基于通用做菜知识回答，"
            "但不要声称已经检索过知识库。"
        )

    if rag_context.status == "hit":
        return "\n".join(
            [
                "后端已经默认检索知识库，并找到了可参考片段。",
                "请优先基于这些片段回答；可以补充通用做菜知识，但不要伪造来源。",
                "如果片段不足以确认某个细节，请明确说明根据当前资料无法确认。",
                "如果引用知识库内容，请在回答末尾注明“来源：知识库”。",
                "预检索知识库片段：",
                render_retrieved_chunks(rag_context.chunks),
            ]
        )

    if rag_context.status == "miss":
        return (
            "后端已经默认检索知识库，但没有找到与本轮输入足够相关的片段。"
            "本轮如果提供了联网搜索上下文，应优先结合联网结果回答，并注明网页来源；"
            "不要声称答案来自知识库。"
        )

    if rag_context.status == "skipped":
        return (
            "后端默认知识库能力已开启，但本轮输入经规则判断不需要检索。"
            "请直接基于当前会话上下文回答，不要声称已经检索过知识库。"
        )

    if rag_context.status == "error":
        return (
            "后端默认知识库检索本轮暂不可用。可以继续基于通用做菜知识回答，"
            "但不要声称已经获得知识库片段。"
        )

    return "本轮知识库状态未知。回答时不要编造知识库来源。"


def _build_web_search_instruction(web_context: WebSearchContext | None) -> str:
    if web_context is None or not web_context.enabled:
        return (
            "本轮没有可用的联网搜索上下文。回答时不要声称已经联网搜索，也不要编造网页来源。"
        )

    if web_context.status == "hit":
        return "\n".join(
            [
                "知识库未检索到相关信息，本轮已自动补充联网搜索结果。",
                "请基于这些搜索结果和通用烹饪知识回答；涉及网页信息时必须在回答末尾注明“来源”。",
                "只能引用下面列出的标题和链接，不要编造来源或链接。",
                "联网搜索结果：",
                _render_web_results(web_context),
            ]
        )

    if web_context.status == "miss":
        return (
            "知识库未检索到相关信息，联网搜索也没有找到可用结果。请明确说明缺少可靠来源，"
            "只能给出通用建议。"
        )

    if web_context.status == "error":
        return (
            "知识库未检索到相关信息，联网搜索本轮失败。请不要声称已获得网页来源；"
            "如继续回答，只能基于通用知识并说明来源不足。"
        )

    return "本轮联网搜索状态不可用。回答时不要编造网页来源。"


def _render_web_results(web_context: WebSearchContext) -> str:
    lines: list[str] = []
    for index, result in enumerate(web_context.results, start=1):
        lines.append(
            f"{index}. {result.title}\n"
            f"链接：{result.link}\n"
            f"摘要：{result.snippet or '无摘要'}"
        )
    return "\n\n".join(lines)


def _build_attachment_instruction(context: AgentTurnContext) -> str:
    if context.attachment_public_ids:
        return (
            "本轮带有附件 ID。需要理解附件时，可以调用 read_attachment_context 工具查看可用摘要。"
        )

    return "本轮没有附件上下文。"
