export type ApiEnvelope<T> = {
  message: string;
  data: T;
};

export type UserProfile = {
  public_id: string;
  username: string;
  email: string;
  status: string;
};

export type AuthPayload = {
  access_token: string;
  token_type: string;
  user: UserProfile;
};

export type ConversationItem = {
  public_id: string;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
  latest_message_at: string | null;
};

export type MessageItem = {
  public_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  status: string;
  message_type: string;
  created_at: string;
};

export type ApiErrorPayload = {
  code?: string;
  message?: string;
  detail?: unknown;
};
