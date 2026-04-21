/*
 * 登录表单组件只负责收集输入和触发事件。
 * 表单的状态、校验和提交结果都由外层 hook 管理。
 */

import type { FormEvent } from "react";
import type { LoginFormState } from "../../types";

type LoginFormProps = {
  form: LoginFormState;
  onFieldChange: (field: keyof LoginFormState, value: string | boolean) => void;
  onForgotPassword: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function LoginForm({
  form,
  onFieldChange,
  onForgotPassword,
  onSubmit,
}: LoginFormProps) {
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

      <label className="field-group">
        <span className="field-row">
          <span className="field-label">密码</span>
          <button className="text-link" type="button" onClick={onForgotPassword}>
            忘记密码？
          </button>
        </span>
        <div className="pill-input">
          <input
            type="password"
            placeholder="请输入密码"
            value={form.password}
            onChange={(event) => onFieldChange("password", event.target.value)}
          />
        </div>
      </label>

      <label className="remember-row">
        <input
          type="checkbox"
          checked={form.remember}
          onChange={(event) => onFieldChange("remember", event.target.checked)}
        />
        <span>记住密码</span>
      </label>

      <button className="primary-button" type="submit">
        登录
      </button>
    </form>
  );
}
