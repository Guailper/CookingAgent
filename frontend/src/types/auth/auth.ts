/*
 * 这里放的是“认证界面和认证业务”会共用的前端类型。
 * 后续如果新增忘记密码、注册页、用户中心，也可以继续复用这里的定义。
 */

export type AuthMode = "login" | "register";

export type NoticeTone = "success" | "error" | "info";

export type SocialProvider = "Google" | "GitHub";

export type Notice = {
  tone: NoticeTone;
  title: string;
  description: string;
};

export type LoginFormState = {
  email: string;
  password: string;
  remember: boolean;
};

export type RegisterFormState = {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
};

export type AuthenticatedUser = {
  publicId: string;
  fullName: string;
  email: string;
  createdAt: string;
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

export type RegisterInput = {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
};
