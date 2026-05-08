/*
 * Raw API payload types used by the frontend service layer.
 * Services translate these payloads into the normalized UI-facing models in `types/chat`.
 */

export type ApiErrorResponse = {
  code?: string;
  message?: string;
  detail?: unknown;
};

export type ApiEnvelope<T> = {
  message: string;
  data: T;
};

export type ApiUserProfile = {
  public_id: string;
  username: string;
  email: string;
  status: string;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ApiAuthResponse = ApiEnvelope<{
  access_token: string;
  token_type: string;
  user: ApiUserProfile;
}>;

export type ApiCurrentUserResponse = ApiEnvelope<ApiUserProfile>;

export type ApiConversationItem = {
  public_id: string;
  title: string;
  status: string;
  latest_message_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ApiConversationResponse = ApiEnvelope<ApiConversationItem>;
export type ApiConversationDetailResponse = ApiEnvelope<ApiConversationItem>;
export type ApiConversationListResponse = ApiEnvelope<ApiConversationItem[]>;

export type ApiAttachmentItem = {
  public_id: string;
  original_name: string;
  file_ext: string;
  mime_type: string;
  file_size: number;
  attachment_kind: "document" | "image";
  parse_status: string;
  created_at: string;
};

export type ApiAttachmentUploadResponse = ApiEnvelope<ApiAttachmentItem[]>;

export type ApiVoiceTranscriptionResponse = ApiEnvelope<{
  transcript: string;
  duration_ms: number | null;
  mime_type: string;
  file_size: number;
}>;

export type ApiMessageItem = {
  public_id: string;
  conversation_id: number;
  user_id: number | null;
  role: string;
  message_type: string;
  content: string;
  status: string;
  extra_metadata: Record<string, unknown> | unknown[] | null;
  attachments: ApiAttachmentItem[];
  created_at: string;
  updated_at: string;
};

export type ApiAgentRunItem = {
  public_id: string;
  intent_type: string;
  workflow_name: string;
  run_status: string;
  model_name: string | null;
  input_snapshot: Record<string, unknown> | unknown[] | null;
  output_snapshot: Record<string, unknown> | unknown[] | null;
  error_code: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ApiMessageResponse = ApiEnvelope<ApiMessageItem>;
export type ApiMessageListResponse = ApiEnvelope<ApiMessageItem[]>;
export type ApiAgentChatResponse = ApiEnvelope<{
  user_message: ApiMessageItem;
  assistant_message: ApiMessageItem;
  agent_run: ApiAgentRunItem;
}>;
