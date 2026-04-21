/*
 * 这个 Hook 把认证页的主要状态和交互都收口在一起。
 * 页面只负责摆放组件，登录与注册流程由这里统一处理。
 */

import { FormEvent, startTransition, useState } from "react";
import {
  AuthServiceError,
  getRememberedCredentials,
  getStoredSession,
  login,
  registerAccount,
  requestPasswordReset,
} from "../../services";
import type {
  AuthMode,
  AuthenticatedUser,
  LoginFormState,
  Notice,
  RegisterFormState,
  SocialProvider,
} from "../../types";

type UseAuthOptions = {
  onAuthenticated?: (user: AuthenticatedUser) => void;
};

const INITIAL_REGISTER_FORM: RegisterFormState = {
  fullName: "",
  email: "",
  password: "",
  confirmPassword: "",
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
  // 当前页面是在登录还是注册模式。
  const [mode, setMode] = useState<AuthMode>("login");

  // 顶部状态提示。
  const [notice, setNotice] = useState<Notice | null>(null);

  // 登录表单状态，默认会读取“记住密码”的本地信息。
  const [loginForm, setLoginForm] = useState<LoginFormState>(() => {
    const remembered = getRememberedCredentials();

    return {
      email: remembered?.email ?? "",
      password: remembered?.password ?? "",
      remember: Boolean(remembered),
    };
  });

  // 注册表单状态。
  const [registerForm, setRegisterForm] = useState<RegisterFormState>(INITIAL_REGISTER_FORM);

  // 这里保留当前登录用户，便于没有外部路由控制时继续扩展。
  const [activeUser, setActiveUser] = useState<AuthenticatedUser | null>(() => {
    return getStoredSession()?.user ?? null;
  });

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
    setNotice({
      tone: "info",
      title: `${provider} 登录暂未接入`,
      description: "当前按钮用于保留界面位置，后续可以在这里接入真实的 OAuth 登录流程。",
    });
  }

  async function handleLoginSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      const session = await login(loginForm);

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
    notice,
    loginForm,
    registerForm,
    activeUser,
    updateLoginForm,
    updateRegisterForm,
    switchMode,
    handleForgotPassword,
    handleSocialAuth,
    handleLoginSubmit,
    handleRegisterSubmit,
  };
}
