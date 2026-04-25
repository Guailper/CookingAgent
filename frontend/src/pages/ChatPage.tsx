/*
 * Chat workspace page.
 * The page stays intentionally thin: the hook owns data fetching and composer orchestration,
 * while the page only wires the returned state into presentation components.
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
    pendingAttachments,
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
    isUploadingAttachments,
    voiceComposerState,
    voiceError,
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
    updateDraft,
    addPendingFiles,
    removePendingFile,
    handleVoiceRecordingChange,
    handleVoiceCaptureError,
    transcribeRecordedAudio,
    sendMessage,
    usePromptSuggestion,
    selectSearchResult,
  } = useWorkspace({ user, onUnauthorized: onLogout });

  function handleWorkspaceClick() {
    closeSettingsMenu();
    closeSearchMenu();
  }

  return (
    <div
      className={`workspace-page ${
        isSidebarOpen ? "workspace-page--sidebar-open" : "workspace-page--sidebar-closed"
      }`}
    >
      <button
        className="workspace-sidebar-toggle"
        type="button"
        aria-label={isSidebarOpen ? "关闭左侧边栏" : "打开左侧边栏"}
        onClick={toggleSidebar}
      >
        <PanelToggleIcon />
      </button>

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

        <div className="workspace-main__content">
          {workspaceNotice && (
            <div className="workspace-main__notice-shell">
              <NoticeBanner notice={workspaceNotice} />
            </div>
          )}

          <div className="workspace-main__body">
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

            <div className="message-input-container">
              <MessageComposer
                value={draft}
                attachments={pendingAttachments}
                isEmptyState={!activeConversation}
                isSending={isSendingMessage}
                isUploadingAttachments={isUploadingAttachments}
                voiceState={voiceComposerState}
                voiceError={voiceError}
                onChange={updateDraft}
                onSelectFiles={addPendingFiles}
                onRemoveAttachment={removePendingFile}
                onVoiceRecordingChange={handleVoiceRecordingChange}
                onVoiceCaptureError={handleVoiceCaptureError}
                onVoiceCaptured={transcribeRecordedAudio}
                onSubmit={() => {
                  void sendMessage();
                }}
              />
            </div>
          </div>
        </div>

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
