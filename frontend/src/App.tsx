import { FormEvent, startTransition, useState } from "react";
import {
  AuthServiceError,
  clearSession,
  getStoredSession,
  getRememberedCredentials,
  login,
  registerAccount,
  requestPasswordReset,
  type AuthenticatedUser,
} from "./services/authService";

type AuthMode = "login" | "register";
type NoticeTone = "success" | "error" | "info";
type SocialProvider = "Google" | "GitHub";

type Notice = {
  tone: NoticeTone;
  title: string;
  description: string;
};

type LoginFormState = {
  email: string;
  password: string;
  remember: boolean;
};

type RegisterFormState = {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
};

const INITIAL_REGISTER_FORM: RegisterFormState = {
  fullName: "",
  email: "",
  password: "",
  confirmPassword: "",
};

function NoticeBanner({ notice }: { notice: Notice }) {
  return (
    <div className={`notice notice--${notice.tone}`} role="status" aria-live="polite">
      <strong>{notice.title}</strong>
      <span>{notice.description}</span>
    </div>
  );
}

function createNoticeFromError(error: unknown): Notice {
  if (error instanceof AuthServiceError) {
    return {
      tone: "error",
      title: error.title,
      description: error.description,
    };
  }

  return {
    tone: "error",
    title: "发生异常",
    description: "处理请求时发生异常，请稍后重试。",
  };
}

function App() {
  const [mode, setMode] = useState<AuthMode>("login");
  const [activeUser, setActiveUser] = useState<AuthenticatedUser | null>(() => {
    return getStoredSession()?.user ?? null;
  });
  const [notice, setNotice] = useState<Notice | null>(null);
  const [loginForm, setLoginForm] = useState<LoginFormState>(() => {
    const remembered = getRememberedCredentials();

    return {
      email: remembered?.email ?? "",
      password: remembered?.password ?? "",
      remember: Boolean(remembered),
    };
  });
  const [registerForm, setRegisterForm] = useState<RegisterFormState>(INITIAL_REGISTER_FORM);

  function switchMode(nextMode: AuthMode) {
    setActiveUser(null);
    setNotice(null);
    startTransition(() => setMode(nextMode));
  }

  async function handleForgotPassword() {
    try {
      await requestPasswordReset(loginForm.email);
      setNotice({
        tone: "info",
        title: "已收到重置密码请求",
        description: "当前仅完成界面接入，后续可连接后端重置密码接口发送邮件或验证码。",
      });
    } catch (error) {
      setNotice(createNoticeFromError(error));
    }
  }

  function handleSocialAuth(provider: SocialProvider) {
    setNotice({
      tone: "info",
      title: `${provider} 登录暂未接入`,
      description: "当前已预留入口以匹配界面设计，下一步可以接入真实的 OAuth 流程。",
    });
  }

  async function handleLoginSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      const session = await login(loginForm);
      const trimmedPassword = loginForm.password.trim();

      setLoginForm((currentState) => ({
        ...currentState,
        email: session.user.email,
        password: trimmedPassword,
      }));
      setActiveUser(session.user);
      setNotice({
        tone: "success",
        title: "登录成功",
        description: "账号验证通过，正在进入工作台。",
      });
    } catch (error) {
      setNotice(createNoticeFromError(error));
    }
  }

  async function handleRegisterSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      const session = await registerAccount(registerForm);

      setRegisterForm(INITIAL_REGISTER_FORM);
      setLoginForm((currentState) => ({
        ...currentState,
        email: session.user.email,
        password: "",
        remember: false,
      }));
      setActiveUser(session.user);
      setNotice({
        tone: "success",
        title: "注册成功",
        description: "账号已经创建完成，并已自动登录。",
      });
    } catch (error) {
      setNotice(createNoticeFromError(error));
    }
  }

  function renderLoginForm() {
    return (
      <>
        <form className="auth-form" onSubmit={handleLoginSubmit}>
          <label className="field-group">
            <span className="field-label">邮箱地址</span>
            <div className="pill-input">
              <input
                type="email"
                placeholder="请输入邮箱地址"
                value={loginForm.email}
                onChange={(event) =>
                  setLoginForm((currentState) => ({
                    ...currentState,
                    email: event.target.value,
                  }))
                }
              />
            </div>
          </label>

          <label className="field-group">
            <span className="field-row">
              <span className="field-label">密码</span>
              <button className="text-link" type="button" onClick={handleForgotPassword}>
                忘记密码？
              </button>
            </span>
            <div className="pill-input">
              <input
                type="password"
                placeholder="请输入密码"
                value={loginForm.password}
                onChange={(event) =>
                  setLoginForm((currentState) => ({
                    ...currentState,
                    password: event.target.value,
                  }))
                }
              />
            </div>
          </label>

          <label className="remember-row">
            <input
              type="checkbox"
              checked={loginForm.remember}
              onChange={(event) =>
                setLoginForm((currentState) => ({
                  ...currentState,
                  remember: event.target.checked,
                }))
              }
            />
            <span>记住密码</span>
          </label>

          <button className="primary-button" type="submit">
            登录
          </button>
        </form>

        <div className="auth-divider" aria-hidden="true">
          <span />
          <p>其他登录方式</p>
          <span />
        </div>

        <div className="social-grid">
          <button className="social-button" type="button" onClick={() => handleSocialAuth("Google")}>
            <GoogleIcon />
            <span>Google 登录</span>
          </button>
          <button className="social-button" type="button" onClick={() => handleSocialAuth("GitHub")}>
            <GitHubIcon />
            <span>GitHub 登录</span>
          </button>
        </div>

        <p className="switch-copy">
          还没有账号？
          <button className="inline-action" type="button" onClick={() => switchMode("register")}>
            立即注册
          </button>
        </p>
      </>
    );
  }

  function renderRegisterForm() {
    return (
      <form className="auth-form auth-form--register" onSubmit={handleRegisterSubmit}>
        <label className="field-group">
          <span className="field-label">昵称</span>
          <div className="pill-input">
            <input
              type="text"
              placeholder="请输入昵称"
              value={registerForm.fullName}
              onChange={(event) =>
                setRegisterForm((currentState) => ({
                  ...currentState,
                  fullName: event.target.value,
                }))
              }
            />
          </div>
        </label>

        <label className="field-group">
          <span className="field-label">邮箱地址</span>
          <div className="pill-input">
            <input
              type="email"
              placeholder="请输入邮箱地址"
              value={registerForm.email}
              onChange={(event) =>
                setRegisterForm((currentState) => ({
                  ...currentState,
                  email: event.target.value,
                }))
              }
            />
          </div>
        </label>

        <label className="field-group">
          <span className="field-label">密码</span>
          <div className="pill-input">
            <input
              type="password"
              placeholder="至少输入 8 位字符"
              value={registerForm.password}
              onChange={(event) =>
                setRegisterForm((currentState) => ({
                  ...currentState,
                  password: event.target.value,
                }))
              }
            />
          </div>
        </label>

        <label className="field-group">
          <span className="field-label">确认密码</span>
          <div className="pill-input">
            <input
              type="password"
              placeholder="请再次输入密码"
              value={registerForm.confirmPassword}
              onChange={(event) =>
                setRegisterForm((currentState) => ({
                  ...currentState,
                  confirmPassword: event.target.value,
                }))
              }
            />
          </div>
        </label>

        <button className="primary-button" type="submit">
          注册账号
        </button>

        <p className="switch-copy">
          已有账号？
          <button className="inline-action" type="button" onClick={() => switchMode("login")}>
            返回登录
          </button>
        </p>
      </form>
    );
  }

  function renderSignedInState() {
    return (
      <section className="success-state">
        <div className="success-mark">
          <CheckIcon />
        </div>
        <h1>登录成功</h1>
        <p>
          欢迎回来，<strong>{activeUser?.fullName}</strong>。账号 <strong>{activeUser?.email}</strong>{" "}
          已通过验证。
        </p>
        <div className="success-actions">
          <button className="primary-button" type="button">
            继续
          </button>
          <button
            className="secondary-button"
            type="button"
            onClick={() => {
              clearSession();
              setActiveUser(null);
              setNotice(null);
            }}
          >
            切换账号
          </button>
        </div>
      </section>
    );
  }

  return (
    <div className="auth-page">
      <div className="backdrop-glow backdrop-glow--left" />
      <div className="backdrop-glow backdrop-glow--right" />
      <div className="backdrop-curve backdrop-curve--one" />
      <div className="backdrop-curve backdrop-curve--two" />

      <main className={`auth-card ${mode === "register" ? "auth-card--register" : ""}`}>
        {activeUser ? (
          renderSignedInState()
        ) : (
          <>
            <header className="auth-copy">
              <h1>{mode === "login" ? "欢迎回来" : "创建账号"}</h1>
              <p>
                {mode === "login"
                  ? "请输入账号信息以继续登录"
                  : "请填写下方信息以创建新的账号"}
              </p>
            </header>

            {notice && <NoticeBanner notice={notice} />}

            {mode === "login" ? renderLoginForm() : renderRegisterForm()}
          </>
        )}
      </main>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M21.8 12.23c0-.7-.06-1.22-.2-1.77H12v3.39h5.64c-.12.84-.79 2.1-2.29 2.95l-.02.11 3.32 2.52.23.02c2.13-1.93 3.36-4.78 3.36-8.22Z"
        fill="currentColor"
        stroke="none"
      />
      <path
        d="M12 22c2.76 0 5.08-.9 6.77-2.44l-3.23-2.65c-.87.59-2.04 1.01-3.54 1.01-2.7 0-4.98-1.75-5.8-4.18l-.11.01-3.45 2.62-.04.1A10.24 10.24 0 0 0 12 22Z"
        fill="currentColor"
        stroke="none"
      />
      <path
        d="M6.2 13.74A6.02 6.02 0 0 1 5.86 12c0-.6.12-1.18.32-1.74l-.01-.12-3.49-2.66-.11.05A9.83 9.83 0 0 0 2 12c0 1.58.38 3.07 1.06 4.47l3.14-2.73Z"
        fill="currentColor"
        stroke="none"
      />
      <path
        d="M12 6.08c1.88 0 3.15.8 3.87 1.48l2.83-2.7C17.07 3.38 14.76 2 12 2a10 10 0 0 0-8.94 5.53l3.61 2.73C7.48 7.83 9.3 6.08 12 6.08Z"
        fill="currentColor"
        stroke="none"
      />
    </svg>
  );
}

function GitHubIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 2C6.48 2 2 6.59 2 12.24c0 4.52 2.87 8.36 6.84 9.71.5.1.68-.22.68-.49 0-.24-.01-1.05-.01-1.9-2.78.62-3.37-1.21-3.37-1.21-.45-1.18-1.11-1.49-1.11-1.49-.91-.64.07-.63.07-.63 1 .07 1.53 1.06 1.53 1.06.9 1.57 2.35 1.12 2.92.85.09-.67.35-1.12.63-1.37-2.22-.26-4.56-1.14-4.56-5.06 0-1.12.39-2.03 1.03-2.75-.1-.26-.45-1.31.1-2.73 0 0 .84-.28 2.75 1.05A9.3 9.3 0 0 1 12 6.84a9.3 9.3 0 0 1 2.5.35c1.9-1.33 2.74-1.05 2.74-1.05.55 1.42.2 2.47.1 2.73.64.72 1.03 1.63 1.03 2.75 0 3.93-2.34 4.8-4.58 5.05.36.32.68.94.68 1.9 0 1.38-.01 2.49-.01 2.83 0 .27.18.59.69.49A10.25 10.25 0 0 0 22 12.24C22 6.59 17.52 2 12 2Z"
        fill="currentColor"
        stroke="none"
      />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m5 12.5 4.2 4.2L19 7.8" />
    </svg>
  );
}

export default App;
