/* 登录成功后的确认态。后续如果接入真实首页跳转，可以从这里继续扩展。 */

import type { AuthenticatedUser } from "../../types";
import { CheckIcon } from "./AuthIcons";

type SignedInStateProps = {
  user: AuthenticatedUser;
  onContinue: () => void;
  onSwitchAccount: () => void;
};

export function SignedInState({
  user,
  onContinue,
  onSwitchAccount,
}: SignedInStateProps) {
  return (
    <section className="success-state">
      <div className="success-mark">
        <CheckIcon />
      </div>
      <h1>登录成功</h1>
      <p>
        欢迎回来，<strong>{user.fullName}</strong>。当前账号 <strong>{user.email}</strong>{" "}
        已通过验证。
      </p>
      <div className="success-actions">
        <button className="primary-button" type="button" onClick={onContinue}>
          继续
        </button>
        <button className="secondary-button" type="button" onClick={onSwitchAccount}>
          切换账号
        </button>
      </div>
    </section>
  );
}
