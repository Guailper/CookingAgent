/* 注册表单组件只处理输入呈现，不处理提交成功后的业务逻辑。 */

import type { FormEvent } from "react";
import type { RegisterFormState } from "../../types";

type RegisterFormProps = {
  form: RegisterFormState;
  codeCooldown: number;
  isSendingCode: boolean;
  onFieldChange: (field: keyof RegisterFormState, value: string) => void;
  onSendEmailCode: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function RegisterForm({
  form,
  codeCooldown,
  isSendingCode,
  onFieldChange,
  onSendEmailCode,
  onSubmit,
}: RegisterFormProps) {
  const sendCodeText =
    codeCooldown > 0 ? `${codeCooldown}s 后重发` : isSendingCode ? "发送中" : "发送验证码";

  return (
    <form className="auth-form auth-form--register" onSubmit={onSubmit}>
      <label className="field-group">
        <span className="field-label">昵称</span>
        <div className="pill-input">
          <input
            type="text"
            placeholder="请输入昵称"
            value={form.fullName}
            onChange={(event) => onFieldChange("fullName", event.target.value)}
          />
        </div>
      </label>

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
      </label>

      <label className="field-group">
        <span className="field-label">密码</span>
        <div className="pill-input">
          <input
            type="password"
            placeholder="至少输入 8 位字符"
            value={form.password}
            onChange={(event) => onFieldChange("password", event.target.value)}
          />
        </div>
      </label>

      <label className="field-group">
        <span className="field-label">确认密码</span>
        <div className="pill-input">
          <input
            type="password"
            placeholder="请再次输入密码"
            value={form.confirmPassword}
            onChange={(event) => onFieldChange("confirmPassword", event.target.value)}
          />
        </div>
      </label>

      <button className="primary-button" type="submit">
        注册账号
      </button>
    </form>
  );
}
