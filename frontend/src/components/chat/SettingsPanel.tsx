/*
 * 设置面板承载账号资料、头像、密码和偏好入口。
 * 这里直接调用认证服务完成用户资料修改，避免把表单细节扩散到页面层。
 */

import { useEffect, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import {
  AuthServiceError,
  changeCurrentUserPassword,
  updateCurrentUserProfile,
  updateStoredAvatar,
} from "../../services";
import type { AuthenticatedUser, ChangePasswordInput, Notice, SettingsView } from "../../types";

type SettingsPanelProps = {
  user: AuthenticatedUser;
  activeView: SettingsView | null;
  onClose: () => void;
  onLogout: () => void;
  onUserChange: (user: AuthenticatedUser) => void;
};

const INITIAL_PASSWORD_FORM: ChangePasswordInput = {
  currentPassword: "",
  newPassword: "",
  confirmPassword: "",
};

function getAvatarLabel(user: AuthenticatedUser) {
  return user.fullName.slice(0, 1).toUpperCase();
}

function createNoticeFromError(error: unknown): Notice {
  if (error instanceof AuthServiceError) {
    return {
      tone: "error",
      title: error.title,
      description: error.description,
    };
  }

  return {
    tone: "error",
    title: "操作失败",
    description: "处理设置时发生异常，请稍后重试。",
  };
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
  onUserChange,
}: SettingsPanelProps) {
  const [profileName, setProfileName] = useState(user.fullName);
  const [passwordForm, setPasswordForm] = useState(INITIAL_PASSWORD_FORM);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  useEffect(() => {
    setProfileName(user.fullName);
  }, [user.fullName]);

  if (!activeView) {
    return null;
  }

  async function handleProfileSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSavingProfile(true);
    setNotice(null);

    try {
      const nextUser = await updateCurrentUserProfile({ fullName: profileName });
      onUserChange({
        ...nextUser,
        avatarUrl: user.avatarUrl ?? nextUser.avatarUrl,
      });
      setNotice({
        tone: "success",
        title: "资料已更新",
        description: "昵称已经同步到当前账号。",
      });
    } catch (error) {
      setNotice(createNoticeFromError(error));
    } finally {
      setIsSavingProfile(false);
    }
  }

  async function handlePasswordSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsChangingPassword(true);
    setNotice(null);

    try {
      await changeCurrentUserPassword(passwordForm);
      setPasswordForm(INITIAL_PASSWORD_FORM);
      setNotice({
        tone: "success",
        title: "密码已更新",
        description: "下次登录时请使用新密码。",
      });
    } catch (error) {
      setNotice(createNoticeFromError(error));
    } finally {
      setIsChangingPassword(false);
    }
  }

  function updatePasswordField(field: keyof ChangePasswordInput, value: string) {
    setPasswordForm((currentValue) => ({
      ...currentValue,
      [field]: value,
    }));
  }

  function handleAvatarChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";

    if (!file) {
      return;
    }

    if (!file.type.startsWith("image/")) {
      setNotice({
        tone: "error",
        title: "头像格式不支持",
        description: "请选择 PNG、JPG、WebP 等图片文件。",
      });
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const avatarUrl = typeof reader.result === "string" ? reader.result : null;
      if (!avatarUrl) {
        return;
      }

      updateStoredAvatar(user.publicId, avatarUrl);
      onUserChange({ ...user, avatarUrl });
      setNotice({
        tone: "success",
        title: "头像已更新",
        description: "头像已保存在当前浏览器。",
      });
    };
    reader.readAsDataURL(file);
  }

  function handleRemoveAvatar() {
    updateStoredAvatar(user.publicId, null);
    onUserChange({ ...user, avatarUrl: null });
    setNotice({
      tone: "success",
      title: "头像已移除",
      description: "当前账号已恢复为文字头像。",
    });
  }

  function renderAccountSettings() {
    return (
      <div className="settings-form-stack">
        <div className="settings-profile-head">
          <div className="settings-avatar-preview">
            {user.avatarUrl ? <img src={user.avatarUrl} alt="当前头像" /> : getAvatarLabel(user)}
          </div>
          <div className="settings-profile-head__actions">
            <label className="secondary-action-button settings-upload-button">
              上传头像
              <input type="file" accept="image/*" onChange={handleAvatarChange} />
            </label>
            <button className="text-action-button" type="button" onClick={handleRemoveAvatar}>
              移除头像
            </button>
          </div>
        </div>

        <form className="settings-form" onSubmit={handleProfileSubmit}>
          <label className="settings-field">
            <span>昵称</span>
            <input
              type="text"
              value={profileName}
              onChange={(event) => setProfileName(event.target.value)}
            />
          </label>

          <label className="settings-field">
            <span>登录邮箱</span>
            <input type="email" value={user.email} readOnly />
          </label>

          <button className="secondary-action-button" type="submit" disabled={isSavingProfile}>
            {isSavingProfile ? "保存中" : "保存资料"}
          </button>
        </form>

        <form className="settings-form" onSubmit={handlePasswordSubmit}>
          <strong>修改密码</strong>
          <label className="settings-field">
            <span>当前密码</span>
            <input
              type="password"
              value={passwordForm.currentPassword}
              onChange={(event) => updatePasswordField("currentPassword", event.target.value)}
            />
          </label>
          <label className="settings-field">
            <span>新密码</span>
            <input
              type="password"
              value={passwordForm.newPassword}
              onChange={(event) => updatePasswordField("newPassword", event.target.value)}
            />
          </label>
          <label className="settings-field">
            <span>确认新密码</span>
            <input
              type="password"
              value={passwordForm.confirmPassword}
              onChange={(event) => updatePasswordField("confirmPassword", event.target.value)}
            />
          </label>
          <button className="secondary-action-button" type="submit" disabled={isChangingPassword}>
            {isChangingPassword ? "更新中" : "更新密码"}
          </button>
        </form>
      </div>
    );
  }

  function renderPanelContent() {
    if (activeView === "account") {
      return renderAccountSettings();
    }

    if (activeView === "appearance") {
      return (
        <div className="settings-card-list">
          <section className="settings-card">
            <strong>侧栏模式</strong>
            <p>可通过左上角按钮展开或收起侧栏，适配不同屏幕宽度。</p>
          </section>
          <section className="settings-card">
            <strong>界面风格</strong>
            <p>当前采用浅色工作台风格，后续可继续接入主题切换。</p>
          </section>
        </div>
      );
    }

    return (
      <div className="settings-card-list">
        <section className="settings-card">
          <strong>活动提醒</strong>
          <p>右上角通知按钮现在会展示系统提醒和使用建议。</p>
        </section>
        <section className="settings-card">
          <strong>对话提示</strong>
          <p>新对话页会保留推荐问题，帮助快速开始一次烹饪咨询。</p>
        </section>
      </div>
    );
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

      {notice && (
        <div className={`settings-notice settings-notice--${notice.tone}`}>
          <strong>{notice.title}</strong>
          <span>{notice.description}</span>
        </div>
      )}

      <div className="settings-panel__content">{renderPanelContent()}</div>

      <div className="settings-panel__footer">
        <button className="secondary-action-button" type="button" onClick={onLogout}>
          退出登录
        </button>
      </div>
    </aside>
  );
}
