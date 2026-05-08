"""Recipe formatting tool."""


def format_recipe_plan(raw_plan: str) -> str:
    """Normalize a recipe draft into a readable Markdown answer."""

    text = (raw_plan or "").strip()
    if not text:
        return "还缺少食材、人数或口味偏好，请补充后我再整理菜谱。"

    return text
