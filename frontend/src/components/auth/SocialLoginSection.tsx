/* 社交登录区域单独拆分，后续接入真实 OAuth 时只需要改这里和服务层。 */

import type { SocialProvider } from "../../types";
import { GitHubIcon, GoogleIcon } from "./AuthIcons";

type SocialLoginSectionProps = {
  onSocialAuth: (provider: SocialProvider) => void;
};

export function SocialLoginSection({ onSocialAuth }: SocialLoginSectionProps) {
  return (
    <>
      <div className="auth-divider" aria-hidden="true">
        <span />
        <p>其他登录方式</p>
        <span />
      </div>

      <div className="social-grid">
        <button className="social-button" type="button" onClick={() => onSocialAuth("Google")}>
          <GoogleIcon />
          <span>Google 登录</span>
        </button>
        <button className="social-button" type="button" onClick={() => onSocialAuth("GitHub")}>
          <GitHubIcon />
          <span>GitHub 登录</span>
        </button>
      </div>
    </>
  );
}
