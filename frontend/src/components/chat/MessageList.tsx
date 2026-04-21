/*
 * 对话消息列表。
 * 这个组件只负责把当前会话的标题、摘要和消息气泡渲染出来，
 * 不直接关心消息是来自本地模拟还是后端接口。
 *
 * 消息数量增加后的滚动边界由父容器和消息列表样式共同控制，
 * 目标是只让消息区内部滚动，而不是把底部输入框挤出当前视口。
 */

import type { ChatConversation, ChatMessage } from "../../types";

type MessageListProps = {
  conversation: ChatConversation;
};

function getMessageRoleLabel(message: ChatMessage) {
  if (message.role === "user") {
    return "你";
  }

  if (message.role === "system") {
    return "系统";
  }

  return "轻灵厨房";
}

export function MessageList({ conversation }: MessageListProps) {
  return (
    <section className="message-panel">
      {/* 顶部区域概括当前会话，方便用户知道自己正在查看哪段内容。 */}
      {/* <header className="message-panel__header">
        <div>
          <span className="workspace-badge workspace-badge--soft">当前对话</span>
          <h2>{conversation.title}</h2>
          <p>{conversation.summary}</p>
        </div>
        <small>最后更新于 {conversation.updatedAt}</small>
      </header> */}

      {/* 消息列表为空时也给出明确说明，避免用户误以为加载失败。 */}
      <div className="message-list">
        {conversation.messages.length > 0 ? (
          conversation.messages.map((message) => (
            <article
              key={message.id}
              className={`message-bubble ${
                message.role === "user" ? "message-bubble--user" : "message-bubble--assistant"
              }`}
            >
              <header className="message-bubble__meta">
                <span className="message-bubble__role">{getMessageRoleLabel(message)}</span>
                <time>{message.createdAt}</time>
              </header>
              <p>{message.content}</p>
            </article>
          ))
        ) : (
          <div className="message-list__empty">
            这个对话还没有消息，输入内容后会自动保存到后端并显示在这里。
          </div>
        )}
      </div>
    </section>
  );
}
