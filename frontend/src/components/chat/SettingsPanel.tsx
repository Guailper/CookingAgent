/*
 * 设置面板会根据当前选中的设置项展示不同内容。
 * 现在先用静态内容承接不同设置页面的 UI 入口。
 */

import type { AuthenticatedUser, SettingsView } from "../../types";

type SettingsPanelProps = {
  user: AuthenticatedUser;
  activeView: SettingsView | null;
  onClose: () => void;
  onLogout: () => void;
};

function renderPanelContent(activeView: SettingsView, user: AuthenticatedUser) {
  if (activeView === "account") {
    return (
      <>
        <p className="settings-panel__lead">这里展示当前登录用户的基础信息与账号状态。</p>
        <div className="settings-card-list">
          <section className="settings-card">
            <strong>头像昵称</strong>
            <p>{user.fullName}</p>
          </section>
          <section className="settings-card">
            <strong>邮箱地址</strong>
            <p>{user.email}</p>
          </section>
          <section className="settings-card">
            <strong>账号状态</strong>
            <p>已登录，当前状态正常。</p>
          </section>
        </div>
      </>
    );
  }

  if (activeView === "appearance") {
    return (
      <>
        <p className="settings-panel__lead">这里用于管理布局与界面偏好，方便后续增加更多外观设置。</p>
        <div className="settings-card-list">
          <section className="settings-card">
            <strong>侧栏模式</strong>
            <p>支持展开和收起，适合不同屏幕宽度下的操作习惯。</p>
          </section>
          <section className="settings-card">
            <strong>主界面风格</strong>
            <p>当前采用柔和浅色主题，后续可扩展暗色模式或自定义主题。</p>
          </section>
        </div>
      </>
    );
  }

  return (
    <>
      <p className="settings-panel__lead">这里用于管理系统提醒、活动消息和后续的推送策略。</p>
      <div className="settings-card-list">
        <section className="settings-card">
          <strong>活动提醒</strong>
          <p>当前为默认开启，后续可细分为推荐、活动和任务提醒。</p>
        </section>
        <section className="settings-card">
          <strong>对话提示</strong>
          <p>近期推测建议会在新对话时展示，后续可支持手动关闭。</p>
        </section>
      </div>
    </>
  );
}

function getPanelTitle(activeView: SettingsView) {
  if (activeView === "account") {
    return "账号设置";
  }

  if (activeView === "appearance") {
    return "界面偏好";
  }

  return "通知设置";
}

export function SettingsPanel({
  user,
  activeView,
  onClose,
  onLogout,
}: SettingsPanelProps) {
  if (!activeView) {
    return null;
  }

  return (
    <aside className="settings-panel">
      <div className="settings-panel__header">
        <div>
          <span className="workspace-badge workspace-badge--soft">设置面板</span>
          <h3>{getPanelTitle(activeView)}</h3>
        </div>
        <button className="text-action-button" type="button" onClick={onClose}>
          关闭
        </button>
      </div>

      <div className="settings-panel__content">{renderPanelContent(activeView, user)}</div>

      <div className="settings-panel__footer">
        <button className="secondary-action-button" type="button" onClick={onLogout}>
          退出登录
        </button>
      </div>
    </aside>
  );
}
