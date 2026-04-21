/*
 * 主界面顶部工具栏。
 * 这里负责品牌信息、搜索入口和右上角快捷操作。
 * 搜索框会根据用户输入展示半透明结果列表，帮助快速跳转历史会话或推荐话题。
 */

import type { KeyboardEvent, MouseEvent } from "react";
import type { WorkspaceSearchResult } from "../../types";
import { BellIcon, HelpIcon, SearchIcon } from "./WorkspaceIcons";

type WorkspaceTopBarProps = {
  searchKeyword: string;
  searchResults: WorkspaceSearchResult[];
  isSearchMenuOpen: boolean;
  onSearchChange: (value: string) => void;
  onSearchFocus: () => void;
  onCloseSearchMenu: () => void;
  onSelectSearchResult: (result: WorkspaceSearchResult) => void;
};

function getResultKindLabel(result: WorkspaceSearchResult) {
  if (result.kind === "conversation") {
    return "最近对话";
  }

  return "推荐话题";
}

export function WorkspaceTopBar({
  searchKeyword,
  searchResults,
  isSearchMenuOpen,
  onSearchChange,
  onSearchFocus,
  onCloseSearchMenu,
  onSelectSearchResult,
}: WorkspaceTopBarProps) {
  function stopHeaderClick(event: MouseEvent<HTMLElement>) {
    // 阻止顶部区域点击冒泡到主容器，避免点搜索结果时先把列表关掉。
    event.stopPropagation();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      onCloseSearchMenu();
    }
  }

  return (
    <header className="workspace-topbar" onClick={stopHeaderClick}>
      {/* 左侧区域只保留系统标题与说明，避免和悬浮边栏按钮互相挤占。 */}
      <div className="workspace-topbar__left">
        <div className="workspace-brand">
          <strong>轻灵厨房</strong>
          <span>为每一次灵感下厨提供帮助</span>
        </div>
      </div>

      {/* 中间区域承接真实搜索输入，并在输入后展示半透明结果列表。 */}
      <div className="workspace-search-shell">
        <label
          className={`workspace-search ${isSearchMenuOpen ? "workspace-search--active" : ""}`}
        >
          <SearchIcon />
          <input
            type="text"
            value={searchKeyword}
            placeholder="搜索最近对话、推荐话题或烹饪关键词..."
            onChange={(event) => onSearchChange(event.target.value)}
            onFocus={onSearchFocus}
            onKeyDown={handleKeyDown}
          />
        </label>

        {isSearchMenuOpen && (
          <div className="workspace-search-results" role="listbox" aria-label="搜索结果">
            {searchResults.length > 0 ? (
              searchResults.map((result) => (
                <button
                  key={result.id}
                  className="workspace-search-result"
                  type="button"
                  onClick={() => onSelectSearchResult(result)}
                >
                  <span className="workspace-search-result__tag">
                    {getResultKindLabel(result)}
                  </span>
                  <strong>{result.title}</strong>
                  <p>{result.description}</p>
                </button>
              ))
            ) : (
              <div className="workspace-search-results__empty">
                没有找到匹配内容，可以换一个食材、菜名或需求试试。
              </div>
            )}
          </div>
        )}
      </div>

      {/* 右侧区域保留通知和帮助入口，维持顶部工具栏的信息层级。 */}
      <div className="workspace-topbar__actions">
        <button className="icon-button" type="button" aria-label="查看提醒">
          <BellIcon />
        </button>
        <button className="icon-button" type="button" aria-label="打开帮助">
          <HelpIcon />
        </button>
      </div>
    </header>
  );
}
