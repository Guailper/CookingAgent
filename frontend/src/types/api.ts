/*
 * 这个文件集中定义前后端接口通信会用到的数据结构。
 * 把认证、会话、消息相关的原始接口类型放在一起，方便联调时快速确认字段含义。
 * 页面层和组件层尽量不要直接依赖这些“后端原始结构”，而是交给服务层做二次转换。
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

export type ApiMessageItem = {
  public_id: string;
  conversation_id: number;
  user_id: number | null;
  role: string;
  message_type: string;
  content: string;
  status: string;
  extra_metadata: Record<string, unknown> | unknown[] | null;
  created_at: string;
  updated_at: string;
};

export type ApiMessageResponse = ApiEnvelope<ApiMessageItem>;

export type ApiMessageListResponse = ApiEnvelope<ApiMessageItem[]>;
