/* 邮箱快捷登录区域，点击后会切换到邮箱验证码登录。 */

import type { SocialProvider } from "../../types";
import { GoogleIcon, QQMailIcon } from "./AuthIcons";

type SocialLoginSectionProps = {
  onSocialAuth: (provider: SocialProvider) => void;
};

export function SocialLoginSection({ onSocialAuth }: SocialLoginSectionProps) {
  return (
    <>
      <div className="auth-divider" aria-hidden="true">
        <span />
        <p>邮箱快捷登录</p>
        <span />
      </div>

      <div className="social-grid">
        <button className="social-button" type="button" onClick={() => onSocialAuth("GoogleMail")}>
          <GoogleIcon />
          <span>谷歌邮箱登录</span>
        </button>
        <button className="social-button" type="button" onClick={() => onSocialAuth("QQMail")}>
          <QQMailIcon />
          <span>QQ 邮箱登录</span>
        </button>
      </div>
    </>
  );
}
