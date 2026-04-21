/*
 * 认证服务层：
 * 1. 负责和后端接口通信
 * 2. 负责本地 session / remember 信息的存取
 * 3. 负责把后端返回的数据转换成前端更容易使用的结构
 *
 * 页面和组件尽量不要直接写 fetch，而是统一走这里。
 */

import type {
  ApiAuthResponse,
  ApiCurrentUserResponse,
  ApiErrorResponse,
  ApiUserProfile,
} from "../../types";
import type {
  AuthenticatedUser,
  AuthSession,
  LoginInput,
  RegisterInput,
  RememberedCredentials,
} from "../../types";

type StoredSession = AuthSession;

const REMEMBERED_KEY = "cooking-agent.remembered";
const SESSION_KEY = "cooking-agent.session";
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "/api/v1").replace(/\/$/, "");

export class AuthServiceError extends Error {
  constructor(
    public readonly code: string,
    public readonly title: string,
    public readonly description: string,
  ) {
    super(description);
    this.name = "AuthServiceError";
  }
}

function canUseStorage() {
  return typeof window !== "undefined" && "localStorage" in window;
}

function normalizeEmail(value: string) {
  return value.trim().toLowerCase();
}

function readJson<T>(key: string, fallback: T) {
  if (!canUseStorage()) {
    return fallback;
  }

  try {
    const rawValue = window.localStorage.getItem(key);
    return rawValue ? (JSON.parse(rawValue) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key: string, value: unknown) {
  if (!canUseStorage()) {
    return;
  }

  window.localStorage.setItem(key, JSON.stringify(value));
}

function clearStorageKey(key: string) {
  if (!canUseStorage()) {
    return;
  }

  window.localStorage.removeItem(key);
}

function toPublicUser(profile: ApiUserProfile): AuthenticatedUser {
  return {
    publicId: profile.public_id,
    fullName: profile.username,
    email: profile.email,
    createdAt: profile.created_at,
  };
}

function getAuthHeaders(accessToken?: string) {
  return {
    "Content-Type": "application/json",
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
  };
}

function persistSession(session: StoredSession) {
  writeJson(SESSION_KEY, session);
}

function toAuthServiceError(
  payload: ApiErrorResponse | null,
  status: number,
): AuthServiceError {
  const code = payload?.code ?? `http_${status}`;
  const backendMessage = payload?.message ?? "请求失败，请稍后重试。";

  switch (code) {
    case "EMAIL_ALREADY_EXISTS":
    case "USER_CREATE_CONFLICT":
      return new AuthServiceError(
        code,
        "邮箱已被注册",
        "请使用其他邮箱，或返回登录已有账号。",
      );
    case "INVALID_CREDENTIALS":
      return new AuthServiceError(
        code,
        "登录失败",
        "邮箱或密码不正确，请检查后重试。",
      );
    case "AUTH_REQUIRED":
    case "INVALID_ACCESS_TOKEN":
    case "USER_NOT_FOUND":
      return new AuthServiceError(
        code,
        "登录状态已失效",
        "当前登录状态已失效，请重新登录。",
      );
    case "USER_DISABLED":
      return new AuthServiceError(
        code,
        "账号不可用",
        "当前账号状态不可用，请联系管理员处理。",
      );
    default:
      return new AuthServiceError(
        code,
        status >= 500 ? "服务暂时不可用" : "请求未完成",
        backendMessage,
      );
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new AuthServiceError(
      "network_error",
      "连接后端失败",
      "无法连接到后端服务，请确认前后端都已经启动。",
    );
  }

  const payload = (await response.json().catch(() => null)) as ApiErrorResponse | T | null;

  if (!response.ok) {
    throw toAuthServiceError(payload as ApiErrorResponse | null, response.status);
  }

  return payload as T;
}

export function getRememberedCredentials() {
  const remembered = readJson<RememberedCredentials | null>(REMEMBERED_KEY, null);

  if (
    remembered &&
    typeof remembered.email === "string" &&
    typeof remembered.password === "string"
  ) {
    return remembered;
  }

  return null;
}

export function getStoredSession() {
  const session = readJson<StoredSession | null>(SESSION_KEY, null);

  if (
    session &&
    typeof session.accessToken === "string" &&
    session.user &&
    typeof session.user.email === "string"
  ) {
    return session;
  }

  return null;
}

export function clearSession() {
  clearStorageKey(SESSION_KEY);
}

export async function login(input: LoginInput): Promise<AuthSession> {
  const email = normalizeEmail(input.email);
  const password = input.password.trim();

  if (!email || !password) {
    throw new AuthServiceError(
      "missing_credentials",
      "缺少登录信息",
      "请输入邮箱和密码后再登录。",
    );
  }

  const response = await requestJson<ApiAuthResponse>("/auth/login", {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ email, password }),
  });

  if (input.remember) {
    writeJson(REMEMBERED_KEY, { email, password });
  } else {
    clearStorageKey(REMEMBERED_KEY);
  }

  const session = {
    accessToken: response.data.access_token,
    user: toPublicUser(response.data.user),
  };

  persistSession(session);
  return session;
}

export async function registerAccount(input: RegisterInput): Promise<AuthSession> {
  const fullName = input.fullName.trim();
  const email = normalizeEmail(input.email);
  const password = input.password.trim();
  const confirmPassword = input.confirmPassword.trim();

  if (!fullName || !email || !password || !confirmPassword) {
    throw new AuthServiceError(
      "missing_fields",
      "请完善表单",
      "创建账号前需要填写所有字段。",
    );
  }

  if (password.length < 8) {
    throw new AuthServiceError(
      "weak_password",
      "密码太短",
      "请至少输入 8 位字符，以便与真实注册流程保持一致。",
    );
  }

  if (password !== confirmPassword) {
    throw new AuthServiceError(
      "password_mismatch",
      "两次密码不一致",
      "请重新输入确认密码，确保两次填写一致。",
    );
  }

  const response = await requestJson<ApiAuthResponse>("/auth/register", {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      username: fullName,
      email,
      password,
    }),
  });

  const session = {
    accessToken: response.data.access_token,
    user: toPublicUser(response.data.user),
  };

  persistSession(session);
  return session;
}

export async function getCurrentUser(): Promise<AuthenticatedUser> {
  const session = getStoredSession();

  if (!session?.accessToken) {
    throw new AuthServiceError(
      "missing_session",
      "尚未登录",
      "当前没有可用的登录状态。",
    );
  }

  const response = await requestJson<ApiCurrentUserResponse>("/auth/me", {
    method: "GET",
    headers: getAuthHeaders(session.accessToken),
  });

  const nextSession = {
    ...session,
    user: toPublicUser(response.data),
  };

  persistSession(nextSession);
  return nextSession.user;
}

export async function requestPasswordReset(email: string) {
  const normalizedEmail = normalizeEmail(email);

  if (!normalizedEmail) {
    throw new AuthServiceError(
      "missing_email",
      "请先输入邮箱",
      "请输入邮箱地址，系统才能发起找回密码流程。",
    );
  }

  // 当前项目还没有接入真实的“忘记密码”接口。
  // 这里先保留参数校验与函数入口，后续接接口时只需要补充请求即可。
}
