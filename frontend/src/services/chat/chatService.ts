/*
 * Chat service layer:
 * 1. Talks to the backend conversation, message, attachment, and voice APIs.
 * 2. Normalizes raw API payloads into UI-friendly frontend models.
 * 3. Keeps lightweight workspace-only helpers such as prompt suggestions and local search.
 */

import type {
  ApiAgentChatResponse,
  ApiAttachmentItem,
  ApiAttachmentUploadResponse,
  ApiConversationDetailResponse,
  ApiConversationItem,
  ApiConversationListResponse,
  ApiConversationResponse,
  ApiErrorResponse,
  ApiMessageItem,
  ApiMessageListResponse,
  ApiVoiceTranscriptionResponse,
} from "../../types";
import type {
  ChatAttachment,
  ChatAttachmentKind,
  ChatConversation,
  ChatMessage,
  ChatMessageRole,
  PendingAttachment,
  PromptSuggestion,
  SettingsMenuItem,
  WorkspaceSearchResult,
} from "../../types";
import { getStoredSession } from "../auth";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "/api/v1").replace(/\/$/, "");
const MAX_COMPOSER_ATTACHMENTS = 5;
const MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024;
const DEFAULT_VOICE_UPLOAD_FILENAME = "voice-input.webm";

const SUPPORTED_ATTACHMENT_EXTENSIONS = new Set([
  ".pdf",
  ".doc",
  ".docx",
  ".ppt",
  ".pptx",
  ".txt",
  ".jpg",
  ".jpeg",
  ".png",
  ".webp",
]);

const VOICE_UPLOAD_EXTENSION_BY_MIME_TYPE: Array<[string, string]> = [
  ["audio/webm", ".webm"],
  ["audio/wav", ".wav"],
  ["audio/wave", ".wav"],
  ["audio/x-wav", ".wav"],
  ["audio/mpeg", ".mp3"],
  ["audio/mp3", ".mp3"],
  ["audio/mp4", ".m4a"],
  ["audio/m4a", ".m4a"],
  ["audio/x-m4a", ".m4a"],
];

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

function getFileExtension(fileName: string) {
  const lastDotIndex = fileName.lastIndexOf(".");
  return lastDotIndex >= 0 ? fileName.slice(lastDotIndex).toLocaleLowerCase() : "";
}

function resolveVoiceUploadFilename(audioBlob: Blob) {
  const normalizedMimeType = audioBlob.type.toLocaleLowerCase();
  const matchedExtension = VOICE_UPLOAD_EXTENSION_BY_MIME_TYPE.find(([mimeType]) =>
    normalizedMimeType.startsWith(mimeType),
  )?.[1];

  return `voice-input${matchedExtension ?? getFileExtension(DEFAULT_VOICE_UPLOAD_FILENAME)}`;
}

function createLocalId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `pending-${crypto.randomUUID()}`;
  }

  return `pending-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
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

function summarizeMessage(message: ChatMessage) {
  if (message.content.trim()) {
    return summarizeContent(message.content);
  }

  if (message.attachments.length === 1) {
    return `已附带文件：${message.attachments[0].name}`;
  }

  if (message.attachments.length > 1) {
    return `已附带 ${message.attachments.length} 个文件`;
  }

  return "新的消息";
}

function createConversationSummary(
  conversation: ApiConversationItem,
  messages: ChatMessage[],
  hasLoadedMessages: boolean,
) {
  if (messages.length > 0) {
    return summarizeMessage(messages[messages.length - 1]);
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

function mapApiAttachment(item: ApiAttachmentItem): ChatAttachment {
  return {
    id: item.public_id,
    name: item.original_name,
    extension: item.file_ext,
    mimeType: item.mime_type,
    size: item.file_size,
    kind: item.attachment_kind,
    parseStatus: item.parse_status,
  };
}

function mapApiMessage(item: ApiMessageItem): ChatMessage {
  return {
    id: item.public_id,
    role: toChatMessageRole(item.role),
    content: item.content,
    createdAt: formatMessageTime(item.created_at),
    status: item.status,
    messageType: item.message_type,
    attachments: item.attachments.map(mapApiAttachment),
    extraMetadata:
      item.extra_metadata && !Array.isArray(item.extra_metadata)
        ? (item.extra_metadata as Record<string, unknown>)
        : null,
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

function getAuthorizationHeaders() {
  const session = getStoredSession();

  if (!session?.accessToken) {
    throw new ChatServiceError(
      "missing_session",
      "登录状态已失效",
      "当前没有可用的登录会话，请重新登录后再继续操作。",
    );
  }

  return {
    Authorization: `Bearer ${session.accessToken}`,
  };
}

function getJsonAuthHeaders() {
  return {
    "Content-Type": "application/json",
    ...getAuthorizationHeaders(),
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
        "消息不能为空",
        "请输入内容或添加附件后再发送消息。",
      );
    case "ATTACHMENT_LIMIT_EXCEEDED":
      return new ChatServiceError(code, "附件数量超出限制", backendMessage);
    case "ATTACHMENT_NOT_FOUND":
      return new ChatServiceError(code, "附件不存在", backendMessage);
    case "ATTACHMENT_ALREADY_BOUND":
      return new ChatServiceError(code, "附件已绑定消息", backendMessage);
    case "ATTACHMENT_REQUIRED":
      return new ChatServiceError(code, "缺少附件", backendMessage);
    case "EMPTY_FILE":
      return new ChatServiceError(code, "文件内容为空", backendMessage);
    case "UNSUPPORTED_FILE_TYPE":
      return new ChatServiceError(code, "文件类型不支持", backendMessage);
    case "UNSUPPORTED_AUDIO_TYPE":
      return new ChatServiceError(code, "语音格式不支持", backendMessage);
    case "EMPTY_AUDIO_FILE":
      return new ChatServiceError(code, "未检测到语音内容", backendMessage);
    case "FILE_TOO_LARGE":
    case "AUDIO_FILE_TOO_LARGE":
      return new ChatServiceError(code, "文件过大", backendMessage);
    case "AUDIO_DURATION_EXCEEDED":
      return new ChatServiceError(code, "语音时长过长", backendMessage);
    case "VOICE_TRANSCRIBE_NOT_CONFIGURED":
      return new ChatServiceError(code, "语音转写未配置", backendMessage);
    case "VOICE_TRANSCRIBE_LOCAL_DEPENDENCY_MISSING":
      return new ChatServiceError(code, "本地语音依赖未安装", backendMessage);
    case "VOICE_TRANSCRIBE_LOCAL_MODEL_LOAD_FAILED":
      return new ChatServiceError(code, "本地语音模型加载失败", backendMessage);
    case "VOICE_TRANSCRIBE_LOCAL_RUNTIME_FAILED":
      return new ChatServiceError(code, "本地语音转写失败", backendMessage);
    case "VOICE_TRANSCRIBE_PROVIDER_UNSUPPORTED":
    case "VOICE_TRANSCRIBE_UPSTREAM_FAILED":
    case "VOICE_TRANSCRIBE_UPSTREAM_UNAVAILABLE":
    case "VOICE_TRANSCRIBE_INVALID_RESPONSE":
    case "VOICE_TRANSCRIBE_EMPTY_RESULT":
      return new ChatServiceError(code, "语音转写失败", backendMessage);
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
      "当前无法连接到后端服务，请确认前后端都已经正常启动。",
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
        ...conversation.messages.flatMap((message) =>
          message.attachments.map((attachment) => attachment.name),
        ),
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

export function formatAttachmentSize(size: number) {
  if (size < 1024) {
    return `${size} B`;
  }

  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }

  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function resolveLocalAttachmentKind(file: File): ChatAttachmentKind {
  const extension = getFileExtension(file.name);

  if ([".jpg", ".jpeg", ".png", ".webp"].includes(extension) || file.type.startsWith("image/")) {
    return "image";
  }

  return "document";
}

export function createPendingAttachment(file: File): PendingAttachment {
  return {
    localId: createLocalId(),
    file,
    name: file.name,
    mimeType: file.type || "application/octet-stream",
    size: file.size,
    kind: resolveLocalAttachmentKind(file),
    status: "pending",
    uploadedId: null,
  };
}

export function validateAttachmentSelection(files: File[], existingCount: number) {
  if (existingCount + files.length > MAX_COMPOSER_ATTACHMENTS) {
    throw new ChatServiceError(
      "ATTACHMENT_LIMIT_EXCEEDED",
      "附件数量超出限制",
      `单条消息最多上传 ${MAX_COMPOSER_ATTACHMENTS} 个附件。`,
    );
  }

  for (const file of files) {
    const extension = getFileExtension(file.name);

    if (!SUPPORTED_ATTACHMENT_EXTENSIONS.has(extension)) {
      throw new ChatServiceError(
        "UNSUPPORTED_FILE_TYPE",
        "文件类型不支持",
        "当前仅支持 PDF、Office 文档、TXT，以及常见图片格式。",
      );
    }

    if (file.size > MAX_ATTACHMENT_SIZE_BYTES) {
      throw new ChatServiceError(
        "FILE_TOO_LARGE",
        "文件过大",
        `文件“${file.name}”超过 10MB 限制。`,
      );
    }
  }
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
  return mergeMessagesIntoConversation(conversation, [message]);
}

export function mergeMessagesIntoConversation(
  conversation: ChatConversation,
  messages: ChatMessage[],
): ChatConversation {
  if (messages.length === 0) {
    return conversation;
  }

  const latestMessageAt = new Date().toISOString();
  const latestMessage = messages[messages.length - 1];

  return {
    ...conversation,
    summary: summarizeMessage(latestMessage),
    updatedAt: formatConversationTime(latestMessageAt),
    latestMessageAt,
    hasLoadedMessages: true,
    messages: [...conversation.messages, ...messages],
  };
}

export async function listRemoteConversations(): Promise<ChatConversation[]> {
  const response = await requestJson<ApiConversationListResponse>("/conversations", {
    method: "GET",
    headers: getJsonAuthHeaders(),
  });

  return response.data.map((conversation) => mapApiConversation(conversation));
}

export async function getRemoteConversation(conversationId: string): Promise<ChatConversation> {
  const [conversationResponse, messagesResponse] = await Promise.all([
    requestJson<ApiConversationDetailResponse>(`/conversations/${conversationId}`, {
      method: "GET",
      headers: getJsonAuthHeaders(),
    }),
    requestJson<ApiMessageListResponse>(`/conversations/${conversationId}/messages`, {
      method: "GET",
      headers: getJsonAuthHeaders(),
    }),
  ]);

  const messages = messagesResponse.data.map(mapApiMessage);

  return mapApiConversation(conversationResponse.data, messages, true);
}

export async function createRemoteConversation(title: string): Promise<ChatConversation> {
  const response = await requestJson<ApiConversationResponse>("/conversations", {
    method: "POST",
    headers: getJsonAuthHeaders(),
    body: JSON.stringify({ title: title.trim() || "新的美食灵感" }),
  });

  return mapApiConversation(response.data, [], true);
}

export async function uploadConversationAttachments(
  conversationId: string,
  files: File[],
): Promise<ChatAttachment[]> {
  const formData = new FormData();

  for (const file of files) {
    formData.append("files", file, file.name);
  }

  const response = await requestJson<ApiAttachmentUploadResponse>(
    `/conversations/${conversationId}/attachments`,
    {
      method: "POST",
      headers: getAuthorizationHeaders(),
      body: formData,
    },
  );

  return response.data.map(mapApiAttachment);
}

export async function removeRemoteAttachment(attachmentId: string) {
  await requestJson<{ message: string }>(`/attachments/${attachmentId}`, {
    method: "DELETE",
    headers: getAuthorizationHeaders(),
  });
}

export async function transcribeVoiceToText(audioBlob: Blob) {
  const formData = new FormData();
  formData.append("file", audioBlob, resolveVoiceUploadFilename(audioBlob));
  formData.append("language", "zh");

  const response = await requestJson<ApiVoiceTranscriptionResponse>("/voice/transcriptions", {
    method: "POST",
    headers: getAuthorizationHeaders(),
    body: formData,
  });

  return {
    transcript: response.data.transcript,
    durationMs: response.data.duration_ms,
    mimeType: response.data.mime_type,
    fileSize: response.data.file_size,
  };
}

type SendRemoteMessageOptions = {
  content: string;
  attachmentIds?: string[];
  extraMetadata?: Record<string, unknown>;
};

export async function sendAgentMessage(
  conversationId: string,
  options: SendRemoteMessageOptions,
): Promise<{
  userMessage: ChatMessage;
  assistantMessage: ChatMessage;
}> {
  const normalizedContent = options.content.trim();
  const normalizedAttachmentIds = (options.attachmentIds ?? []).filter(Boolean);

  if (!normalizedContent && normalizedAttachmentIds.length === 0) {
    throw new ChatServiceError(
      "EMPTY_MESSAGE_CONTENT",
      "消息不能为空",
      "请输入内容或添加附件后再发送消息。",
    );
  }

  const response = await requestJson<ApiAgentChatResponse>("/agent/chat", {
    method: "POST",
    headers: getJsonAuthHeaders(),
    body: JSON.stringify({
      conversation_id: conversationId,
      content: normalizedContent,
      attachment_ids: normalizedAttachmentIds,
      extra_metadata: options.extraMetadata ?? null,
    }),
  });

  return {
    userMessage: mapApiMessage(response.data.user_message),
    assistantMessage: mapApiMessage(response.data.assistant_message),
  };
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
