export type AuthenticatedUser = {
  fullName: string;
  email: string;
  createdAt: string;
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

type StoredAccount = AuthenticatedUser & {
  password: string;
};

const ACCOUNTS_KEY = "cooking-agent.accounts";
const REMEMBERED_KEY = "cooking-agent.remembered";

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

function readAccounts() {
  const accounts = readJson<StoredAccount[]>(ACCOUNTS_KEY, []);
  return Array.isArray(accounts) ? accounts : [];
}

function toPublicUser(account: StoredAccount): AuthenticatedUser {
  return {
    fullName: account.fullName,
    email: account.email,
    createdAt: account.createdAt,
  };
}

export function getDemoAccountCount() {
  return readAccounts().length;
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

export async function login(input: LoginInput): Promise<AuthenticatedUser> {
  const email = normalizeEmail(input.email);
  const password = input.password.trim();

  if (!email || !password) {
    throw new AuthServiceError(
      "missing_credentials",
      "缺少登录信息",
      "请输入邮箱和密码后再登录。",
    );
  }

  const matchedAccount = readAccounts().find(
    (account) => account.email === email && account.password === password,
  );

  if (!matchedAccount) {
    throw new AuthServiceError(
      "account_not_found",
      "账号不存在",
      "请先注册账号，或确认保存的邮箱和密码是否正确。",
    );
  }

  if (input.remember) {
    writeJson(REMEMBERED_KEY, { email, password });
  } else {
    clearStorageKey(REMEMBERED_KEY);
  }

  return toPublicUser(matchedAccount);
}

export async function registerAccount(input: RegisterInput): Promise<{
  createdUser: AuthenticatedUser;
  nextLogin: RememberedCredentials;
}> {
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

  const accounts = readAccounts();

  if (accounts.some((account) => account.email === email)) {
    throw new AuthServiceError(
      "email_exists",
      "邮箱已被注册",
      "请使用其他邮箱，或返回登录已有账号。",
    );
  }

  const nextAccount: StoredAccount = {
    fullName,
    email,
    password,
    createdAt: new Date().toISOString(),
  };

  writeJson(ACCOUNTS_KEY, [...accounts, nextAccount]);

  return {
    createdUser: toPublicUser(nextAccount),
    nextLogin: {
      email,
      password,
    },
  };
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
}
