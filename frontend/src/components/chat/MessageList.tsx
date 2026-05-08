/*
 * Conversation message list.
 * The component renders message bubbles plus any attachments already bound to those messages.
 */

import { formatAttachmentSize } from "../../services";
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

              {message.content && <p>{message.content}</p>}

              {message.attachments.length > 0 && (
                <div className="message-bubble__attachments">
                  {message.attachments.map((attachment) => (
                    <div key={attachment.id} className="message-bubble__attachment">
                      <strong>{attachment.name}</strong>
                      <span>
                        {attachment.kind === "image" ? "图片" : "文档"} ·{" "}
                        {formatAttachmentSize(attachment.size)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </article>
          ))
        ) : (
          <div className="message-list__empty">
            这个对话还没有消息，输入内容或添加附件后会自动保存到后端并显示在这里。
          </div>
        )}
      </div>
    </section>
  );
}
