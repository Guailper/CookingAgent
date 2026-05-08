/* 认证卡片顶部的标题区，只负责根据当前模式展示文案。 */

import type { AuthMode } from "../../types";

type AuthHeaderProps = {
  mode: AuthMode;
};

export function AuthHeader({ mode }: AuthHeaderProps) {
  const title = mode === "login" ? "欢迎回来" : "创建账号";
  const description =
    mode === "login" ? "请输入账号信息以继续登录。" : "请填写下方信息以创建新的账号。";

  return (
    <header className="auth-copy">
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  );
}
