/*
 * 登录表单组件只负责收集输入和触发事件。
 * 表单状态、校验和提交结果由外层 hook 管理。
 */

import type { FormEvent } from "react";
import type { LoginFormState, LoginMethod } from "../../types";

type LoginFormProps = {
  form: LoginFormState;
  loginMethod: LoginMethod;
  codeCooldown: number;
  isSendingCode: boolean;
  codeMessage: string | null;
  onFieldChange: (field: keyof LoginFormState, value: string | boolean) => void;
  onLoginMethodChange: (method: LoginMethod) => void;
  onForgotPassword: () => void;
  onSendEmailCode: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function LoginForm({
  form,
  loginMethod,
  codeCooldown,
  isSendingCode,
  codeMessage,
  onFieldChange,
  onLoginMethodChange,
  onForgotPassword,
  onSendEmailCode,
  onSubmit,
}: LoginFormProps) {
  const isEmailCodeLogin = loginMethod === "emailCode";
  const sendCodeText =
    codeCooldown > 0 ? `${codeCooldown}s 后重发` : isSendingCode ? "发送中" : "发送验证码";

  return (
    <form className="auth-form" onSubmit={onSubmit}>
      <label className="field-group">
        <span className="field-label">邮箱地址</span>
        <div className="pill-input">
          <input
            type="email"
            placeholder="请输入邮箱地址"
            value={form.email}
            onChange={(event) => onFieldChange("email", event.target.value)}
          />
        </div>
      </label>

      {isEmailCodeLogin ? (
        <div className="field-group">
          <label className="field-group">
            <span className="field-label">邮箱验证码</span>
            <div className="code-input-row">
              <div className="pill-input">
                <input
                  type="text"
                  inputMode="numeric"
                  placeholder="请输入验证码"
                  value={form.emailCode}
                  onChange={(event) => onFieldChange("emailCode", event.target.value)}
                />
              </div>
              <button
                className="code-button"
                type="button"
                disabled={isSendingCode || codeCooldown > 0}
                onClick={onSendEmailCode}
              >
                {sendCodeText}
              </button>
            </div>
            {codeMessage && <span className="field-hint">{codeMessage}</span>}
          </label>

          <button
            className="login-method-link"
            type="button"
            onClick={() => onLoginMethodChange("password")}
          >
            使用密码登录
          </button>
        </div>
      ) : (
        <>
          <div className="field-group">
            <span className="field-row">
              <span className="field-label">密码</span>
              <button className="text-link" type="button" onClick={onForgotPassword}>
                忘记密码？
              </button>
            </span>

            <label>
              <div className="pill-input">
                <input
                  type="password"
                  placeholder="请输入密码"
                  value={form.password}
                  onChange={(event) => onFieldChange("password", event.target.value)}
                />
              </div>
            </label>

            <button
              className="login-method-link"
              type="button"
              onClick={() => onLoginMethodChange("emailCode")}
            >
              使用验证码登录
            </button>
          </div>

          <label className="remember-row">
            <input
              type="checkbox"
              checked={form.remember}
              onChange={(event) => onFieldChange("remember", event.target.checked)}
            />
            <span>记住密码</span>
          </label>
        </>
      )}

      <button className="primary-button" type="submit">
        登录
      </button>
    </form>
  );
}
