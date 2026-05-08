/*
 * 这个 Hook 把认证页的主要状态和交互收口在一起。
 * 页面只负责摆放组件，登录、注册和邮箱验证码流程由这里统一处理。
 */

import { FormEvent, startTransition, useEffect, useState } from "react";
import {
  AuthServiceError,
  getRememberedCredentials,
  getStoredSession,
  login,
  loginWithEmailCode,
  registerAccount,
  requestPasswordReset,
  sendEmailCode,
} from "../../services";
import type {
  AuthMode,
  AuthenticatedUser,
  LoginFormState,
  LoginMethod,
  Notice,
  RegisterFormState,
  SocialProvider,
} from "../../types";

type UseAuthOptions = {
  onAuthenticated?: (user: AuthenticatedUser) => void;
};

const CODE_COOLDOWN_SECONDS = 60;

const INITIAL_REGISTER_FORM: RegisterFormState = {
  fullName: "",
  email: "",
  password: "",
  confirmPassword: "",
  emailCode: "",
};

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

export function useAuth({ onAuthenticated }: UseAuthOptions = {}) {
  const [mode, setMode] = useState<AuthMode>("login");
  const [loginMethod, setLoginMethod] = useState<LoginMethod>("password");
  const [notice, setNotice] = useState<Notice | null>(null);
  const [loginCodeCooldown, setLoginCodeCooldown] = useState(0);
  const [registerCodeCooldown, setRegisterCodeCooldown] = useState(0);
  const [isSendingLoginCode, setIsSendingLoginCode] = useState(false);
  const [isSendingRegisterCode, setIsSendingRegisterCode] = useState(false);

  const [loginForm, setLoginForm] = useState<LoginFormState>(() => {
    const remembered = getRememberedCredentials();

    return {
      email: remembered?.email ?? "",
      password: remembered?.password ?? "",
      emailCode: "",
      remember: Boolean(remembered),
    };
  });

  const [registerForm, setRegisterForm] = useState<RegisterFormState>(INITIAL_REGISTER_FORM);
  const [activeUser, setActiveUser] = useState<AuthenticatedUser | null>(() => {
    return getStoredSession()?.user ?? null;
  });

  useEffect(() => {
    if (loginCodeCooldown <= 0) {
      return;
    }

    const timer = window.setTimeout(() => {
      setLoginCodeCooldown((currentValue) => Math.max(0, currentValue - 1));
    }, 1000);

    return () => window.clearTimeout(timer);
  }, [loginCodeCooldown]);

  useEffect(() => {
    if (registerCodeCooldown <= 0) {
      return;
    }

    const timer = window.setTimeout(() => {
      setRegisterCodeCooldown((currentValue) => Math.max(0, currentValue - 1));
    }, 1000);

    return () => window.clearTimeout(timer);
  }, [registerCodeCooldown]);

  function updateLoginForm(field: keyof LoginFormState, value: string | boolean) {
    setLoginForm((currentState) => ({
      ...currentState,
      [field]: value,
    }));
  }

  function updateRegisterForm(field: keyof RegisterFormState, value: string) {
    setRegisterForm((currentState) => ({
      ...currentState,
      [field]: value,
    }));
  }

  function switchMode(nextMode: AuthMode) {
    setNotice(null);
    startTransition(() => setMode(nextMode));
  }

  function switchLoginMethod(nextMethod: LoginMethod) {
    setNotice(null);
    setLoginMethod(nextMethod);
  }

  async function handleForgotPassword() {
    try {
      await requestPasswordReset(loginForm.email);
      setNotice({
        tone: "info",
        title: "已提交找回密码请求",
        description: "当前前端已预留入口，后续接入后端接口后即可发送邮件或验证码。",
      });
    } catch (error) {
      setNotice(createNoticeFromError(error));
    }
  }

  function handleSocialAuth(provider: SocialProvider) {
    const providerText = provider === "QQMail" ? "QQ 邮箱" : "谷歌邮箱";
    const domainHint = provider === "QQMail" ? "建议使用 @qq.com 或 @foxmail.com 邮箱。" : "建议使用 @gmail.com 邮箱。";

    setMode("login");
    setLoginMethod("emailCode");
    setNotice({
      tone: "info",
      title: `${providerText}验证码登录`,
      description: `${domainHint}输入邮箱后获取验证码即可登录。`,
    });
  }

  async function handleSendLoginEmailCode() {
    try {
      setIsSendingLoginCode(true);
      await sendEmailCode(loginForm.email, "login");
      setLoginCodeCooldown(CODE_COOLDOWN_SECONDS);
      setNotice({
        tone: "success",
        title: "验证码已发送",
        description: "请查看邮箱并在有效期内完成登录。",
      });
    } catch (error) {
      setNotice(createNoticeFromError(error));
    } finally {
      setIsSendingLoginCode(false);
    }
  }

  async function handleSendRegisterEmailCode() {
    try {
      setIsSendingRegisterCode(true);
      await sendEmailCode(registerForm.email, "register");
      setRegisterCodeCooldown(CODE_COOLDOWN_SECONDS);
      setNotice({
        tone: "success",
        title: "验证码已发送",
        description: "请查看邮箱并在有效期内完成注册。",
      });
    } catch (error) {
      setNotice(createNoticeFromError(error));
    } finally {
      setIsSendingRegisterCode(false);
    }
  }

  async function handleLoginSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      const session =
        loginMethod === "emailCode"
          ? await loginWithEmailCode({
              email: loginForm.email,
              emailCode: loginForm.emailCode,
            })
          : await login(loginForm);

      setActiveUser(session.user);
      setNotice({
        tone: "success",
        title: "登录成功",
        description: "账号验证通过，正在进入系统主界面。",
      });

      onAuthenticated?.(session.user);
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
        emailCode: "",
        remember: false,
      }));
      setActiveUser(session.user);
      setNotice({
        tone: "success",
        title: "注册成功",
        description: "账号已创建完成，正在进入系统主界面。",
      });

      onAuthenticated?.(session.user);
    } catch (error) {
      setNotice(createNoticeFromError(error));
    }
  }

  return {
    mode,
    loginMethod,
    notice,
    loginForm,
    registerForm,
    activeUser,
    loginCodeCooldown,
    registerCodeCooldown,
    isSendingLoginCode,
    isSendingRegisterCode,
    updateLoginForm,
    updateRegisterForm,
    switchMode,
    switchLoginMethod,
    handleForgotPassword,
    handleSocialAuth,
    handleSendLoginEmailCode,
    handleSendRegisterEmailCode,
    handleLoginSubmit,
    handleRegisterSubmit,
  };
}
