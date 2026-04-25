/*
 * Frontend-facing chat types.
 * These are the normalized shapes consumed by hooks and components, not raw API payloads.
 */

export type ChatMessageRole = "user" | "assistant" | "system";

export type ChatAttachmentKind = "document" | "image";

export type ChatAttachment = {
  id: string;
  name: string;
  extension: string;
  mimeType: string;
  size: number;
  kind: ChatAttachmentKind;
  parseStatus: string;
};

export type PendingAttachmentStatus = "pending" | "uploaded";

export type PendingAttachment = {
  localId: string;
  file: File;
  name: string;
  mimeType: string;
  size: number;
  kind: ChatAttachmentKind;
  status: PendingAttachmentStatus;
  uploadedId: string | null;
};

export type VoiceComposerState = "idle" | "recording" | "transcribing" | "error";

export type ChatMessage = {
  id: string;
  role: ChatMessageRole;
  content: string;
  createdAt: string;
  status: string;
  messageType: string;
  attachments: ChatAttachment[];
  extraMetadata?: Record<string, unknown> | null;
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
