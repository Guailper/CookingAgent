/*
 * 这个 Hook 统一管理主界面的交互状态。
 * 这一版已经把会话列表、会话详情和消息发送接到了后端接口，
 * 同时继续保留搜索、推荐气泡和设置菜单这类更偏前端体验层的交互逻辑。
 */

import { useEffect, useState } from "react";
import {
  ChatServiceError,
  buildConversationTitle,
  createPromptSuggestions,
  createRemoteConversation,
  createSettingsMenuItems,
  getRemoteConversation,
  isChatSessionError,
  listRemoteConversations,
  mergeMessageIntoConversation,
  searchWorkspaceContent,
  sendRemoteMessage,
} from "../../services";
import type {
  AuthenticatedUser,
  ChatConversation,
  Notice,
  PromptSuggestion,
  SettingsView,
  WorkspaceSearchResult,
} from "../../types";

type UseWorkspaceOptions = {
  user: AuthenticatedUser;
  onUnauthorized?: () => void;
};

function toWorkspaceNotice(error: unknown): Notice {
  if (error instanceof ChatServiceError) {
    return {
      tone: "error",
      title: error.title,
      description: error.description,
    };
  }

  return {
    tone: "error",
    title: "加载失败",
    description: "处理主界面请求时发生异常，请稍后重试。",
  };
}

function upsertConversation(
  currentConversations: ChatConversation[],
  nextConversation: ChatConversation,
  moveToFront = false,
) {
  const conversationsWithoutTarget = currentConversations.filter(
    (conversation) => conversation.id !== nextConversation.id,
  );

  if (moveToFront) {
    return [nextConversation, ...conversationsWithoutTarget];
  }

  return [...conversationsWithoutTarget, nextConversation];
}

export function useWorkspace({ user, onUnauthorized }: UseWorkspaceOptions) {
  // 控制左侧菜单栏是否处于展开状态。
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  // 控制设置按钮旁的弹出菜单是否显示。
  const [isSettingsMenuOpen, setIsSettingsMenuOpen] = useState(false);

  // 记录当前正在查看的设置面板内容。
  const [activeSettingsView, setActiveSettingsView] = useState<SettingsView | null>(null);

  // 主界面的最近对话列表来自后端，会在进入页面后自动加载。
  const [conversations, setConversations] = useState<ChatConversation[]>([]);

  // 记录当前打开的是哪一段会话；为空表示正在“新对话”欢迎态。
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);

  // 输入框中的草稿内容。
  const [draft, setDraft] = useState("");

  // 顶部搜索框的输入内容。
  const [searchKeyword, setSearchKeyword] = useState("");

  // 控制搜索结果面板是否展开。
  const [isSearchMenuOpen, setIsSearchMenuOpen] = useState(false);

  // 用来向用户展示“会话加载失败”“消息发送失败”等后端请求错误。
  const [workspaceNotice, setWorkspaceNotice] = useState<Notice | null>(null);

  // 防止初始化阶段和发送消息阶段重复触发请求。
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);
  const [isSendingMessage, setIsSendingMessage] = useState(false);

  // 设置菜单项先保留静态配置，后续可以继续扩展。
  const settingsMenuItems = createSettingsMenuItems();

  // 推荐气泡仍然保留在前端层，作为新对话的快捷入口。
  const promptSuggestions = createPromptSuggestions();

  // 根据当前激活的会话 id 找到对应会话数据。
  const activeConversation =
    conversations.find((conversation) => conversation.id === activeConversationId) ?? null;

  // 搜索结果会同时查询历史会话和推荐气泡，帮助用户快速跳转。
  const searchResults = searchWorkspaceContent(searchKeyword, conversations, promptSuggestions);

  useEffect(() => {
    let isMounted = true;

    async function loadConversationList() {
      setIsLoadingConversations(true);
      setWorkspaceNotice(null);

      try {
        const remoteConversations = await listRemoteConversations();

        if (!isMounted) {
          return;
        }

        setConversations(remoteConversations);
      } catch (error) {
        if (!isMounted) {
          return;
        }

        if (isChatSessionError(error)) {
          onUnauthorized?.();
          return;
        }

        setWorkspaceNotice(toWorkspaceNotice(error));
      } finally {
        if (isMounted) {
          setIsLoadingConversations(false);
        }
      }
    }

    void loadConversationList();

    return () => {
      isMounted = false;
    };
  }, [user.publicId]);

  function toggleSidebar() {
    setIsSidebarOpen((currentState) => !currentState);
  }

  function toggleSettingsMenu() {
    setIsSettingsMenuOpen((currentState) => !currentState);
  }

  function closeSettingsMenu() {
    setIsSettingsMenuOpen(false);
  }

  function openSettingsView(view: SettingsView) {
    setActiveSettingsView(view);
    setIsSettingsMenuOpen(false);
  }

  function closeSettingsPanel() {
    setActiveSettingsView(null);
  }

  function updateSearchKeyword(nextKeyword: string) {
    setSearchKeyword(nextKeyword);
    setIsSearchMenuOpen(Boolean(nextKeyword.trim()));
  }

  function openSearchMenu() {
    if (searchKeyword.trim()) {
      setIsSearchMenuOpen(true);
    }
  }

  function closeSearchMenu() {
    setIsSearchMenuOpen(false);
  }

  function clearSearch() {
    setSearchKeyword("");
    setIsSearchMenuOpen(false);
  }

  async function openConversation(conversationId: string) {
    setActiveConversationId(conversationId);
    setWorkspaceNotice(null);

    const targetConversation = conversations.find(
      (conversation) => conversation.id === conversationId,
    );

    if (targetConversation?.hasLoadedMessages) {
      return;
    }

    try {
      const remoteConversation = await getRemoteConversation(conversationId);

      setConversations((currentConversations) =>
        currentConversations.map((conversation) =>
          conversation.id === remoteConversation.id ? remoteConversation : conversation,
        ),
      );
    } catch (error) {
      if (isChatSessionError(error)) {
        onUnauthorized?.();
        return;
      }

      setWorkspaceNotice(toWorkspaceNotice(error));
    }
  }

  function startNewConversation() {
    setActiveConversationId(null);
    setDraft("");
    setWorkspaceNotice(null);
    clearSearch();
  }

  async function sendMessage(promptFromSuggestion?: string) {
    const nextPrompt = (promptFromSuggestion ?? draft).trim();

    if (!nextPrompt || isSendingMessage) {
      return;
    }

    setWorkspaceNotice(null);
    setIsSendingMessage(true);

    let targetConversationId = activeConversationId;
    let createdConversation: ChatConversation | null = null;

    try {
      if (!targetConversationId) {
        createdConversation = await createRemoteConversation(buildConversationTitle(nextPrompt));
        targetConversationId = createdConversation.id;

        setActiveConversationId(createdConversation.id);
        setConversations((currentConversations) =>
          upsertConversation(currentConversations, createdConversation!, true),
        );
      }

      const nextMessage = await sendRemoteMessage(targetConversationId, nextPrompt);

      setConversations((currentConversations) => {
        const currentConversation =
          currentConversations.find((conversation) => conversation.id === targetConversationId) ??
          createdConversation;

        if (!currentConversation) {
          return currentConversations;
        }

        const nextConversation = mergeMessageIntoConversation(currentConversation, nextMessage);

        return upsertConversation(currentConversations, nextConversation, true);
      });

      setDraft("");
      clearSearch();
    } catch (error) {
      if (isChatSessionError(error)) {
        onUnauthorized?.();
        return;
      }

      setWorkspaceNotice(toWorkspaceNotice(error));
    } finally {
      setIsSendingMessage(false);
    }
  }

  async function usePromptSuggestion(suggestion: PromptSuggestion) {
    await sendMessage(suggestion.prompt);
  }

  async function selectSearchResult(result: WorkspaceSearchResult) {
    if (result.kind === "conversation" && result.conversationId) {
      await openConversation(result.conversationId);
    }

    if (result.kind === "suggestion" && result.prompt) {
      await sendMessage(result.prompt);
    }

    clearSearch();
  }

  return {
    user,
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
    isLoadingConversations,
    isSendingMessage,
    setDraft,
    toggleSidebar,
    toggleSettingsMenu,
    closeSettingsMenu,
    openSettingsView,
    closeSettingsPanel,
    updateSearchKeyword,
    openSearchMenu,
    closeSearchMenu,
    clearSearch,
    openConversation,
    startNewConversation,
    sendMessage,
    usePromptSuggestion,
    selectSearchResult,
  };
}
