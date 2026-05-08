/*
 * 欢迎态区域负责展示：
 * 1. 主标题
 * 2. 系统说明
 * 3. 系统猜测的近期对话建议
 */

import type { PromptSuggestion } from "../../types";
import { LeafIcon, PanIcon, SparkIcon } from "./WorkspaceIcons";

type PromptSuggestionsProps = {
  suggestions: PromptSuggestion[];
  onSelectSuggestion: (suggestion: PromptSuggestion) => void;
};

function SuggestionIcon({ icon }: Pick<PromptSuggestion, "icon">) {
  if (icon === "pan") {
    return <PanIcon />;
  }

  if (icon === "leaf") {
    return <LeafIcon />;
  }

  return <SparkIcon />;
}

export function PromptSuggestions({
  suggestions,
  onSelectSuggestion,
}: PromptSuggestionsProps) {
  return (
    <section className="workspace-empty-state">
      {/* 页面主标题与说明文案。 */}
      <div className="workspace-empty-state__hero">
        <span className="workspace-badge">AI 烹饪智能伙伴</span>
        <h1>今天想吃点什么？</h1>
        <p>探索时令食材，精进烹饪技巧，打造流畅的用餐体验。</p>
      </div>

      {/* 建议卡片放在输入框上方，让用户一眼看到系统推荐的话题。 */}
      <div className="workspace-suggestion-grid">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion.id}
            className="suggestion-card"
            type="button"
            onClick={() => onSelectSuggestion(suggestion)}
          >
            <span className="suggestion-card__icon">
              <SuggestionIcon icon={suggestion.icon} />
            </span>
            <strong>{suggestion.title}</strong>
            <p>{suggestion.description}</p>
          </button>
        ))}
      </div>
    </section>
  );
}
