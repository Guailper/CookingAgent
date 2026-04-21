/*
 * 左侧菜单栏负责展示：
 * 1. 品牌与入口
 * 2. 新建会话按钮
 * 3. 最近会话列表
 * 4. 用户信息与设置菜单
 *
 * 侧栏布局采用“顶部内容 + 中部滚动列表 + 底部用户区”的固定骨架。
 * 这样会话数量再多，也只会让中间列表滚动，不会把底部用户区挤出屏幕。
 *
 * 最近会话列表按照当前设计要求只展示单行标题，
 * 避免一条记录占据过多垂直空间，影响侧栏浏览效率。
 */

import type {
  AuthenticatedUser,
  ChatConversation,
  SettingsMenuItem,
  SettingsView,
} from "../../types";
import { ClockIcon, GearIcon, PlusIcon } from "./WorkspaceIcons";

type ChatSidebarProps = {
  user: AuthenticatedUser;
  conversations: ChatConversation[];
  isOpen: boolean;
  isSettingsMenuOpen: boolean;
  activeConversationId: string | null;
  settingsMenuItems: SettingsMenuItem[];
  onNewConversation: () => void;
  onOpenConversation: (conversationId: string) => void;
  onToggleSettingsMenu: () => void;
  onOpenSettingsView: (view: SettingsView) => void;
};

function getAvatarLabel(user: AuthenticatedUser) {
  return user.fullName.slice(0, 1).toUpperCase();
}

export function ChatSidebar({
  user,
  conversations,
  isOpen,
  isSettingsMenuOpen,
  activeConversationId,
  settingsMenuItems,
  onNewConversation,
  onOpenConversation,
  onToggleSettingsMenu,
  onOpenSettingsView,
}: ChatSidebarProps) {
  return (
    <aside className={`workspace-sidebar ${isOpen ? "" : "workspace-sidebar--collapsed"}`}>
      {/* 顶部品牌信息帮助用户快速识别当前所处的产品空间。 */}
      <div className="workspace-sidebar__brand">
        <div className="workspace-sidebar__brand-mark">{getAvatarLabel(user)}</div>
        {isOpen && (
          <div className="workspace-sidebar__brand-copy">
            <span>您的智能厨师</span>
          </div>
        )}
      </div>

      {/* 新对话按钮始终保留，用户可以随时回到欢迎态重新开始。 */}
      <button className="new-conversation-button" type="button" onClick={onNewConversation}>
        <PlusIcon />
        {isOpen && <span>开启新对话</span>}
      </button>

      {/* 最近会话区只保留单行标题，并且独立滚动消化超长列表。 */}
      <div className="workspace-sidebar__section">
        {isOpen && <p className="workspace-sidebar__section-title">最近的菜单对话</p>}

        <div className="workspace-sidebar__history" aria-label="最近会话列表">
          {conversations.map((conversation) => {
            const isActive = conversation.id === activeConversationId;

            return (
              <button
                key={conversation.id}
                className={`history-item ${isActive ? "history-item--active" : ""}`}
                type="button"
                onClick={() => onOpenConversation(conversation.id)}
                title={conversation.title}
              >
                <span className="history-item__icon">
                  <ClockIcon />
                </span>

                {isOpen && (
                  <span className="history-item__copy">
                    <strong>{conversation.title}</strong>
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* 底部用户区域始终锚定在侧栏底边，不参与最近会话列表的滚动。 */}
      <div className="workspace-sidebar__footer">
        <div className="workspace-user">
          <div className="workspace-user__avatar">{getAvatarLabel(user)}</div>

          {isOpen && (
            <div className="workspace-user__copy">
              <strong>{user.fullName}</strong>
              <span>{user.email}</span>
            </div>
          )}
        </div>

        <div className="workspace-settings">
          <button
            className="icon-button"
            type="button"
            aria-label="打开设置菜单"
            onClick={onToggleSettingsMenu}
          >
            <GearIcon />
          </button>

          {isSettingsMenuOpen && (
            <div className="settings-menu" role="menu" aria-label="设置菜单">
              {settingsMenuItems.map((item) => (
                <button
                  key={item.id}
                  className="settings-menu__item"
                  type="button"
                  onClick={() => onOpenSettingsView(item.id)}
                >
                  <strong>{item.label}</strong>
                  <span>{item.description}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
