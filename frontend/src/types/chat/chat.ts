/*
 * 这个文件定义“主界面 / 聊天界面”会用到的核心前端类型。
 * 这些类型已经不是后端原始返回，而是服务层整理后的前端友好结构。
 * 这样组件和 hooks 可以更专注于交互，而不用关心后端字段命名。
 */

export type ChatMessageRole = "user" | "assistant" | "system";

export type ChatMessage = {
  id: string;
  role: ChatMessageRole;
  content: string;
  createdAt: string;
  status: string;
  messageType: string;
};

export type ChatConversation = {
  id: string;
  title: string;
  summary: string;
  status: string;
  createdAt: string;
  updatedAt: string;
  latestMessageAt: string | null;
  hasLoadedMessages: boolean;
  messages: ChatMessage[];
};

export type PromptSuggestion = {
  id: string;
  icon: "spark" | "pan" | "leaf";
  title: string;
  description: string;
  prompt: string;
};

export type SettingsView = "account" | "appearance" | "notifications";

export type SettingsMenuItem = {
  id: SettingsView;
  label: string;
  description: string;
};

export type WorkspaceSearchResult = {
  id: string;
  kind: "conversation" | "suggestion";
  title: string;
  description: string;
  conversationId?: string;
  prompt?: string;
};
