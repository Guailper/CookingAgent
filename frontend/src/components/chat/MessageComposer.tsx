/*
 * 底部输入框区域。
 * 输入框支持普通发送，也会在“新对话欢迎态”下与建议卡片一起工作。
 * 发送按钮会根据输入内容和发送状态切换是否可点击，避免空消息或重复提交。
 *
 * 组件本身只负责输入交互，不负责定位。
 * 真正的“始终贴底”由外层页面容器和样式层共同保证，
 * 这样消息增长时，输入框也不会被推到可视区域之外。
 */

import type { KeyboardEvent } from "react";
import { SendIcon } from "./WorkspaceIcons";

type MessageComposerProps = {
  value: string;
  isEmptyState: boolean;
  isSending?: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function MessageComposer({
  value,
  isEmptyState,
  isSending = false,
  onChange,
  onSubmit,
}: MessageComposerProps) {
  const isSubmitDisabled = !value.trim() || isSending;

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" && !isSubmitDisabled) {
      event.preventDefault();
      onSubmit();
    }
  }

  return (
    <div className={`composer ${isEmptyState ? "composer--floating" : ""}`}>
      <div className="composer__field">
        <input
          type="text"
          value={value}
          placeholder="开启您的美食之旅..."
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
        />
      </div>

      <button
        className="composer__send"
        type="button"
        onClick={onSubmit}
        aria-label={isSending ? "正在发送消息" : "发送消息"}
        disabled={isSubmitDisabled}
      >
        <SendIcon />
      </button>
    </div>
  );
}
