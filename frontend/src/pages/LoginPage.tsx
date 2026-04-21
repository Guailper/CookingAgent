/*
 * 登录页现在只负责认证流程本身。
 * 一旦登录或注册成功，会把控制权交给路由层，直接进入系统主界面。
 */

import { useAuth } from "../hooks";
import type { AuthenticatedUser } from "../types";
import {
  AuthBackground,
  AuthHeader,
  LoginForm,
  NoticeBanner,
  RegisterForm,
  SocialLoginSection,
} from "../components";
import "../styles/auth.css";

type LoginPageProps = {
  onAuthenticated: (user: AuthenticatedUser) => void;
};

export default function LoginPage({ onAuthenticated }: LoginPageProps) {
  const {
    mode,
    notice,
    loginForm,
    registerForm,
    updateLoginForm,
    updateRegisterForm,
    switchMode,
    handleForgotPassword,
    handleSocialAuth,
    handleLoginSubmit,
    handleRegisterSubmit,
  } = useAuth({ onAuthenticated });

  return (
    <div className="auth-page">
      <AuthBackground />

      <main className={`auth-card ${mode === "register" ? "auth-card--register" : ""}`}>
        <AuthHeader mode={mode} />

        {notice && <NoticeBanner notice={notice} />}

        {mode === "login" ? (
          <>
            <LoginForm
              form={loginForm}
              onFieldChange={updateLoginForm}
              onForgotPassword={handleForgotPassword}
              onSubmit={handleLoginSubmit}
            />

            <SocialLoginSection onSocialAuth={handleSocialAuth} />

            <p className="switch-copy">
              还没有账号？
              <button className="inline-action" type="button" onClick={() => switchMode("register")}>
                立即注册
              </button>
            </p>
          </>
        ) : (
          <>
            <RegisterForm
              form={registerForm}
              onFieldChange={updateRegisterForm}
              onSubmit={handleRegisterSubmit}
            />

            <p className="switch-copy">
              已有账号？
              <button className="inline-action" type="button" onClick={() => switchMode("login")}>
                返回登录
              </button>
            </p>
          </>
        )}
      </main>
    </div>
  );
}
