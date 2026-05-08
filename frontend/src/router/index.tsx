/*
 * 这里用一个轻量的本地路由控制来管理“认证页”和“主界面”之间的切换。
 * 和前一版不同的是，这里会在刷新后主动请求后端验证本地 token，
 * 避免只因为 localStorage 里还有旧数据就误判为仍然处于登录态。
 */

import { useEffect, useState } from "react";
import LoginPage from "../pages/LoginPage";
import ChatPage from "../pages/ChatPage";
import { clearSession, getCurrentUser, getStoredSession } from "../services";
import type { AuthenticatedUser } from "../types";

type RouteName = "auth" | "workspace";

const initialSession = getStoredSession();

export default function AppRouter() {
  const [route, setRoute] = useState<RouteName>(initialSession ? "workspace" : "auth");
  const [currentUser, setCurrentUser] = useState<AuthenticatedUser | null>(
    initialSession?.user ?? null,
  );
  const [isRestoringSession, setIsRestoringSession] = useState(Boolean(initialSession));

  useEffect(() => {
    let isMounted = true;

    async function restoreSessionFromBackend() {
      if (!initialSession) {
        setIsRestoringSession(false);
        return;
      }

      try {
        const backendUser = await getCurrentUser();

        if (!isMounted) {
          return;
        }

        setCurrentUser(backendUser);
        setRoute("workspace");
      } catch {
        if (!isMounted) {
          return;
        }

        clearSession();
        setCurrentUser(null);
        setRoute("auth");
      } finally {
        if (isMounted) {
          setIsRestoringSession(false);
        }
      }
    }

    void restoreSessionFromBackend();

    return () => {
      isMounted = false;
    };
  }, []);

  function handleAuthenticated(user: AuthenticatedUser) {
    setCurrentUser(user);
    setRoute("workspace");
  }

  function handleLogout() {
    clearSession();
    setCurrentUser(null);
    setRoute("auth");
  }

  if (isRestoringSession) {
    return (
      <div className="app-boot">
        <div className="app-boot__card">
          <strong>正在恢复登录状态</strong>
          <span>前端正在向后端确认当前会话是否仍然有效。</span>
        </div>
      </div>
    );
  }

  if (route === "workspace" && currentUser) {
    return <ChatPage user={currentUser} onLogout={handleLogout} />;
  }

  return <LoginPage onAuthenticated={handleAuthenticated} />;
}
