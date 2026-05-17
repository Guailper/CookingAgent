"""User long-term memory tools for the LangChain agent."""

from agent.contracts import AgentTurnContext, UserMemoryContextItem


def build_user_memory_search_tool(context: AgentTurnContext):
    """Create a per-turn memory lookup tool from preloaded user memories."""

    def search_user_memory(query: str = "") -> str:
        """Search this user's long-term cooking preferences and constraints."""

        memories = _rank_memories(context.user_memories, query)
        if not memories:
            return "当前没有可用的用户长期记忆。"

        lines = ["用户长期记忆："]
        for index, memory in enumerate(memories, start=1):
            lines.append(
                f"{index}. [{memory.memory_type}] {memory.content}"
                f"（confidence={memory.confidence}）"
            )
        return "\n".join(lines)

    return search_user_memory


def render_user_memories(memories: list[UserMemoryContextItem]) -> str:
    """Render long-term memories for system prompt injection."""

    if not memories:
        return "本轮没有可用的用户长期记忆。"

    lines = ["用户长期记忆如下，回答时优先遵守这些偏好、禁忌、厨具和健康目标："]
    for index, memory in enumerate(memories, start=1):
        lines.append(f"{index}. [{memory.memory_type}] {memory.content}")
    return "\n".join(lines)


def _rank_memories(
    memories: list[UserMemoryContextItem],
    query: str,
) -> list[UserMemoryContextItem]:
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return memories

    scored = [
        (_score_memory(memory, normalized_query), index, memory)
        for index, memory in enumerate(memories)
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    ranked = [memory for score, _, memory in scored if score > 0]
    return ranked or memories


def _score_memory(memory: UserMemoryContextItem, normalized_query: str) -> int:
    content = _normalize_text(memory.content)
    score = 0
    if content and (content in normalized_query or normalized_query in content):
        score += 4

    score += len(set(content.split()) & set(normalized_query.split()))
    return score


def _normalize_text(text: str | None) -> str:
    return " ".join((text or "").strip().lower().split())
