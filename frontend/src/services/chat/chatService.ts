/*
 * 这个服务文件负责两类事情：
 * 1. 把主界面的会话与消息请求真正接到 FastAPI 后端
 * 2. 保留主界面里仍然属于前端增强层的内容，例如推荐气泡、设置菜单和搜索结果整理
 *
 * 这样拆分以后，hooks 和组件层不需要直接关心后端接口字段，只消费这里整理好的前端结构。
 */

import type {
  ApiConversationDetailResponse,
  ApiConversationItem,
  ApiConversationListResponse,
  ApiConversationResponse,
  ApiErrorResponse,
  ApiMessageItem,
  ApiMessageListResponse,
  ApiMessageResponse,
} from "../../types";
import type {
  ChatConversation,
  ChatMessage,
  ChatMessageRole,
  PromptSuggestion,
  SettingsMenuItem,
  WorkspaceSearchResult,
} from "../../types";
import { getStoredSession } from "../auth";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "/api/v1").replace(/\/$/, "");
const TEXT_MESSAGE_TYPE = "text";

export class ChatServiceError extends Error {
  constructor(
    public readonly code: string,
    public readonly title: string,
    public readonly description: string,
  ) {
    super(description);
    this.name = "ChatServiceError";
  }
}

function normalizeKeyword(value: string) {
  return value.trim().toLocaleLowerCase();
}

function formatMessageTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatConversationTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function summarizeContent(content: string) {
  const normalizedContent = content.trim().replace(/\s+/g, " ");

  if (normalizedContent.length <= 28) {
    return normalizedContent;
  }

  return `${normalizedContent.slice(0, 28)}...`;
}

function createConversationSummary(
  conversation: ApiConversationItem,
  messages: ChatMessage[],
  hasLoadedMessages: boolean,
) {
  if (messages.length > 0) {
    return summarizeContent(messages[messages.length - 1].content);
  }

  if (hasLoadedMessages) {
    return "这个对话还没有消息，发送第一条内容后会显示在这里。";
  }

  if (conversation.latest_message_at) {
    return "最近有新的消息记录，点击后可查看完整内容。";
  }

  return "这个对话还没有消息，发送第一条内容后会显示在这里。";
}

function toChatMessageRole(role: string): ChatMessageRole {
  if (role === "assistant") {
    return "assistant";
  }

  if (role === "system") {
    return "system";
  }

  return "user";
}

function mapApiMessage(item: ApiMessageItem): ChatMessage {
  return {
    id: item.public_id,
    role: toChatMessageRole(item.role),
    content: item.content,
    createdAt: formatMessageTime(item.created_at),
    status: item.status,
    messageType: item.message_type,
  };
}

function mapApiConversation(
  item: ApiConversationItem,
  messages: ChatMessage[] = [],
  hasLoadedMessages = false,
): ChatConversation {
  const updatedSource = item.latest_message_at ?? item.updated_at;

  return {
    id: item.public_id,
    title: item.title,
    summary: createConversationSummary(item, messages, hasLoadedMessages),
    status: item.status,
    createdAt: item.created_at,
    updatedAt: formatConversationTime(updatedSource),
    latestMessageAt: item.latest_message_at,
    hasLoadedMessages,
    messages,
  };
}

function getAuthHeaders() {
  const session = getStoredSession();

  if (!session?.accessToken) {
    throw new ChatServiceError(
      "missing_session",
      "登录状态已失效",
      "当前没有可用的登录会话，请重新登录后再继续操作。",
    );
  }

  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${session.accessToken}`,
  };
}

function toChatServiceError(
  payload: ApiErrorResponse | null,
  status: number,
): ChatServiceError {
  const code = payload?.code ?? `http_${status}`;
  const backendMessage = payload?.message ?? "请求未完成，请稍后重试。";

  switch (code) {
    case "AUTH_REQUIRED":
    case "INVALID_ACCESS_TOKEN":
    case "USER_NOT_FOUND":
    case "USER_DISABLED":
    case "missing_session":
      return new ChatServiceError(
        code,
        "登录状态已失效",
        "当前登录状态已经失效，请重新登录后再继续操作。",
      );
    case "CONVERSATION_NOT_FOUND":
      return new ChatServiceError(
        code,
        "未找到对应对话",
        "当前对话可能已被删除或不属于当前用户，请刷新后重试。",
      );
    case "EMPTY_MESSAGE_CONTENT":
      return new ChatServiceError(
        code,
        "消息内容不能为空",
        "请输入内容后再发送消息。",
      );
    default:
      return new ChatServiceError(
        code,
        status >= 500 ? "后端服务暂时不可用" : "请求未完成",
        backendMessage,
      );
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new ChatServiceError(
      "network_error",
      "无法连接后端服务",
      "当前无法连接到后端服务，请确认 FastAPI 服务已经正常启动。",
    );
  }

  const payload = (await response.json().catch(() => null)) as ApiErrorResponse | T | null;

  if (!response.ok) {
    throw toChatServiceError(payload as ApiErrorResponse | null, response.status);
  }

  return payload as T;
}

function buildConversationSearchResults(
  keyword: string,
  conversations: ChatConversation[],
): WorkspaceSearchResult[] {
  return conversations
    .filter((conversation) => {
      const searchableText = [
        conversation.title,
        conversation.summary,
        ...conversation.messages.map((message) => message.content),
      ]
        .join(" ")
        .toLocaleLowerCase();

      return searchableText.includes(keyword);
    })
    .slice(0, 4)
    .map((conversation) => ({
      id: `conversation-result-${conversation.id}`,
      kind: "conversation" as const,
      title: conversation.title,
      description: conversation.summary,
      conversationId: conversation.id,
    }));
}

function buildSuggestionSearchResults(
  keyword: string,
  promptSuggestions: PromptSuggestion[],
): WorkspaceSearchResult[] {
  return promptSuggestions
    .filter((suggestion) => {
      const searchableText = [suggestion.title, suggestion.description, suggestion.prompt]
        .join(" ")
        .toLocaleLowerCase();

      return searchableText.includes(keyword);
    })
    .slice(0, 4)
    .map((suggestion) => ({
      id: `suggestion-result-${suggestion.id}`,
      kind: "suggestion" as const,
      title: suggestion.title,
      description: suggestion.description,
      prompt: suggestion.prompt,
    }));
}

export function isChatSessionError(error: unknown) {
  return (
    error instanceof ChatServiceError &&
    ["AUTH_REQUIRED", "INVALID_ACCESS_TOKEN", "USER_NOT_FOUND", "USER_DISABLED", "missing_session"].includes(
      error.code,
    )
  );
}

export function buildConversationTitle(prompt: string) {
  const trimmed = prompt.trim();

  if (!trimmed) {
    return "新的美食灵感";
  }

  return trimmed.length > 14 ? `${trimmed.slice(0, 14)}...` : trimmed;
}

export function mergeMessageIntoConversation(
  conversation: ChatConversation,
  message: ChatMessage,
): ChatConversation {
  const nextMessages = [...conversation.messages, message];
  const latestMessageAt = new Date().toISOString();

  return {
    ...conversation,
    summary: summarizeContent(message.content),
    updatedAt: formatConversationTime(latestMessageAt),
    latestMessageAt,
    hasLoadedMessages: true,
    messages: nextMessages,
  };
}

export async function listRemoteConversations(): Promise<ChatConversation[]> {
  const response = await requestJson<ApiConversationListResponse>("/conversations", {
    method: "GET",
    headers: getAuthHeaders(),
  });

  return response.data.map((conversation) => mapApiConversation(conversation));
}

export async function getRemoteConversation(conversationId: string): Promise<ChatConversation> {
  const [conversationResponse, messagesResponse] = await Promise.all([
    requestJson<ApiConversationDetailResponse>(`/conversations/${conversationId}`, {
      method: "GET",
      headers: getAuthHeaders(),
    }),
    requestJson<ApiMessageListResponse>(`/conversations/${conversationId}/messages`, {
      method: "GET",
      headers: getAuthHeaders(),
    }),
  ]);

  const messages = messagesResponse.data.map(mapApiMessage);

  return mapApiConversation(conversationResponse.data, messages, true);
}

export async function createRemoteConversation(title: string): Promise<ChatConversation> {
  const response = await requestJson<ApiConversationResponse>("/conversations", {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ title: title.trim() || "新的美食灵感" }),
  });

  // 新建会话刚创建时还没有消息，因此直接标记为已加载空消息列表。
  return mapApiConversation(response.data, [], true);
}

export async function sendRemoteMessage(
  conversationId: string,
  content: string,
): Promise<ChatMessage> {
  const normalizedContent = content.trim();

  if (!normalizedContent) {
    throw new ChatServiceError(
      "EMPTY_MESSAGE_CONTENT",
      "消息内容不能为空",
      "请输入内容后再发送消息。",
    );
  }

  const response = await requestJson<ApiMessageResponse>(`/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      content: normalizedContent,
      message_type: TEXT_MESSAGE_TYPE,
    }),
  });

  return mapApiMessage(response.data);
}

export function createPromptSuggestions(): PromptSuggestion[] {
  return [
    {
      id: "suggestion-menu",
      icon: "spark",
      title: "定制菜单",
      description: "围绕今天的食材与时间，快速生成一套适合你的菜谱建议。",
      prompt: "今天冰箱里有鸡胸肉、土豆和西兰花，帮我安排一份一人食菜单。",
    },
    {
      id: "suggestion-skill",
      icon: "pan",
      title: "掌握技巧",
      description: "聚焦一个烹饪动作，帮助你更快补齐常用做菜技巧。",
      prompt: "我总是掌握不好火候，能不能教我几个家庭炒菜更稳的技巧？",
    },
    {
      id: "suggestion-season",
      icon: "leaf",
      title: "时令推荐",
      description: "结合当季食材和天气，让今天的餐桌更有季节感。",
      prompt: "最近这个季节适合吃什么？请给我三道适合晚餐的家常菜。",
    },
  ];
}

export function createSettingsMenuItems(): SettingsMenuItem[] {
  return [
    {
      id: "account",
      label: "账号设置",
      description: "查看头像、邮箱和账号状态。",
    },
    {
      id: "appearance",
      label: "界面偏好",
      description: "管理布局、侧栏和信息展示风格。",
    },
    {
      id: "notifications",
      label: "通知设置",
      description: "控制提醒、活动消息和提示方式。",
    },
  ];
}

export function searchWorkspaceContent(
  keyword: string,
  conversations: ChatConversation[],
  promptSuggestions: PromptSuggestion[],
): WorkspaceSearchResult[] {
  const normalizedKeyword = normalizeKeyword(keyword);

  if (!normalizedKeyword) {
    return [];
  }

  return [
    ...buildConversationSearchResults(normalizedKeyword, conversations),
    ...buildSuggestionSearchResults(normalizedKeyword, promptSuggestions),
  ].slice(0, 6);
}
