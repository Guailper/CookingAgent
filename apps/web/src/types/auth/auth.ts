/*
 * 认证界面和认证业务共用的前端类型。
 */

export type AuthMode = "login" | "register";

export type LoginMethod = "password" | "emailCode";

export type EmailCodePurpose = "register" | "login";

export type NoticeTone = "success" | "error" | "info";

export type SocialProvider = "GoogleMail" | "QQMail";

export type Notice = {
  tone: NoticeTone;
  title: string;
  description: string;
};

export type LoginFormState = {
  email: string;
  password: string;
  emailCode: string;
  remember: boolean;
};

export type RegisterFormState = {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
  emailCode: string;
};

export type AuthenticatedUser = {
  publicId: string;
  fullName: string;
  email: string;
  createdAt: string;
  avatarUrl?: string | null;
};

export type AuthSession = {
  accessToken: string;
  user: AuthenticatedUser;
};

export type RememberedCredentials = {
  email: string;
  password: string;
};

export type LoginInput = {
  email: string;
  password: string;
  remember: boolean;
};

export type EmailCodeLoginInput = {
  email: string;
  emailCode: string;
};

export type RegisterInput = {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
  emailCode: string;
};

export type UpdateProfileInput = {
  fullName: string;
};

export type ChangePasswordInput = {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
};
