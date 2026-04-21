/*
 * 这是系统主界面页面。
 * 页面结构分成三大块：
 * 1. 左侧可收起的菜单栏
 * 2. 顶部工具栏与搜索结果
 * 3. 右侧主对话区与设置面板
 *
 * 页面本身只负责把 Hook 返回的数据和组件拼起来，
 * 真正的后端请求、状态编排和会话切换逻辑都放在 useWorkspace 里。
 */

import { useWorkspace } from "../hooks";
import type { AuthenticatedUser } from "../types";
import {
  ChatSidebar,
  MessageComposer,
  MessageList,
  NoticeBanner,
  PanelToggleIcon,
  PromptSuggestions,
  SettingsPanel,
  WorkspaceTopBar,
} from "../components";
import "../styles/chat.css";

type ChatPageProps = {
  user: AuthenticatedUser;
  onLogout: () => void;
};

export default function ChatPage({ user, onLogout }: ChatPageProps) {
  const {
    draft,
    conversations,
    activeConversation,
    isSidebarOpen,
    isSettingsMenuOpen,
    activeSettingsView,
    settingsMenuItems,
    promptSuggestions,
    searchKeyword,
    isSearchMenuOpen,
    searchResults,
    workspaceNotice,
    isSendingMessage,
    setDraft,
    toggleSidebar,
    toggleSettingsMenu,
    openSettingsView,
    closeSettingsMenu,
    closeSearchMenu,
    updateSearchKeyword,
    openSearchMenu,
    closeSettingsPanel,
    openConversation,
    startNewConversation,
    sendMessage,
    usePromptSuggestion,
    selectSearchResult,
  } = useWorkspace({ user, onUnauthorized: onLogout });

  function handleWorkspaceClick() {
    // 主内容区的空白点击用于统一收起设置菜单和搜索浮层。
    closeSettingsMenu();
    closeSearchMenu();
  }

  return (
    <div
      className={`workspace-page ${
        isSidebarOpen ? "workspace-page--sidebar-open" : "workspace-page--sidebar-closed"
      }`}
    >
      {/* 将边栏开关提升到页面最外层，按钮位置才能随着边栏宽度一起移动。 */}
      <button
        className="workspace-sidebar-toggle"
        type="button"
        aria-label={isSidebarOpen ? "关闭左侧边栏" : "打开左侧边栏"}
        onClick={toggleSidebar}
      >
        <PanelToggleIcon />
      </button>

      {/* 左侧菜单栏负责展示会话入口、用户资料和设置菜单。 */}
      <ChatSidebar
        user={user}
        conversations={conversations}
        isOpen={isSidebarOpen}
        isSettingsMenuOpen={isSettingsMenuOpen}
        activeConversationId={activeConversation?.id ?? null}
        settingsMenuItems={settingsMenuItems}
        onNewConversation={startNewConversation}
        onOpenConversation={openConversation}
        onToggleSettingsMenu={toggleSettingsMenu}
        onOpenSettingsView={openSettingsView}
      />

      {/* 右侧主工作区负责顶部搜索、消息阅读、输入框和设置面板。 */}
      <section className="workspace-main" onClick={handleWorkspaceClick}>
        <WorkspaceTopBar
          searchKeyword={searchKeyword}
          searchResults={searchResults}
          isSearchMenuOpen={isSearchMenuOpen}
          onSearchChange={updateSearchKeyword}
          onSearchFocus={openSearchMenu}
          onCloseSearchMenu={closeSearchMenu}
          onSelectSearchResult={selectSearchResult}
        />

        {/* 内容层负责锁定主区域高度，避免提示条或长消息把底部输入框向下挤出视口。 */}
        <div className="workspace-main__content">
          {/* 请求失败后的提示放在内容层顶部，但不会参与消息区滚动。 */}
          {workspaceNotice && (
            <div className="workspace-main__notice-shell">
              <NoticeBanner notice={workspaceNotice} />
            </div>
          )}

          {/* 主体部分拆成“可滚动消息区 + 固定输入区”，保证输入框始终贴在主区域底部。 */}
          <div className="workspace-main__body">
            {/* 只有这块区域会随着消息增长而滚动，避免把输入框和设置面板一起顶走。 */}
            <div className="message-scroll-container">
              {activeConversation ? (
                <MessageList conversation={activeConversation} />
              ) : (
                <PromptSuggestions
                  suggestions={promptSuggestions}
                  onSelectSuggestion={usePromptSuggestion}
                />
              )}
            </div>

            {/* 输入框本身不参与滚动，始终占据主工作区的底部固定槽位。 */}
            <div className="message-input-container">
              <MessageComposer
                value={draft}
                isEmptyState={!activeConversation}
                isSending={isSendingMessage}
                onChange={setDraft}
                onSubmit={() => {
                  void sendMessage();
                }}
              />
            </div>
          </div>
        </div>

        {/* 设置面板在用户从设置菜单中选择某一项后打开。 */}
        <SettingsPanel
          user={user}
          activeView={activeSettingsView}
          onClose={closeSettingsPanel}
          onLogout={onLogout}
        />
      </section>
    </div>
  );
}
