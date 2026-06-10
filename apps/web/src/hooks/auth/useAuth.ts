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
  const [loginCodeMessage, setLoginCodeMessage] = useState<string | null>(null);
  const [registerCodeMessage, setRegisterCodeMessage] = useState<string | null>(null);

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
    if (field === "email" || field === "emailCode") {
      setLoginCodeMessage(null);
    }

    setLoginForm((currentState) => ({
      ...currentState,
      [field]: value,
    }));
  }

  function updateRegisterForm(field: keyof RegisterFormState, value: string) {
    if (field === "email" || field === "emailCode") {
      setRegisterCodeMessage(null);
    }

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
    void provider;

    setMode("login");
    setLoginMethod("emailCode");
    setNotice(null);
    setLoginCodeMessage(null);
  }

  async function handleSendLoginEmailCode() {
    try {
      setIsSendingLoginCode(true);
      setLoginCodeCooldown(CODE_COOLDOWN_SECONDS);
      setLoginCodeMessage("验证码发送中，请稍候。");
      await sendEmailCode(loginForm.email, "login");
      setLoginCodeMessage("验证码已发送，请查看邮箱。");
    } catch (error) {
      if (error instanceof AuthServiceError && error.code === "EMAIL_CODE_TOO_FREQUENT") {
        setLoginCodeMessage(`发送过于频繁，请 ${loginCodeCooldown || CODE_COOLDOWN_SECONDS} 秒后再试。`);
      } else {
        setLoginCodeCooldown(0);
        setLoginCodeMessage(null);
        setNotice(createNoticeFromError(error));
      }
    } finally {
      setIsSendingLoginCode(false);
    }
  }

  async function handleSendRegisterEmailCode() {
    try {
      setIsSendingRegisterCode(true);
      setRegisterCodeCooldown(CODE_COOLDOWN_SECONDS);
      setRegisterCodeMessage("验证码发送中，请稍候。");
      await sendEmailCode(registerForm.email, "register");
      setRegisterCodeMessage("验证码已发送，请查看邮箱。");
    } catch (error) {
      if (error instanceof AuthServiceError && error.code === "EMAIL_CODE_TOO_FREQUENT") {
        setRegisterCodeMessage(`发送过于频繁，请 ${registerCodeCooldown || CODE_COOLDOWN_SECONDS} 秒后再试。`);
      } else {
        setRegisterCodeCooldown(0);
        setRegisterCodeMessage(null);
        setNotice(createNoticeFromError(error));
      }
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
    loginCodeMessage,
    registerCodeMessage,
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
