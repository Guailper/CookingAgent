/*
 * Conversation message list.
 * The component renders message bubbles plus any attachments already bound to those messages.
 */

import { useLayoutEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { formatAttachmentSize } from "../../services";
import type { ChatConversation, ChatMessage } from "../../types";

type MessageListProps = {
  conversation: ChatConversation;
};

function getMessageRoleLabel(message: ChatMessage) {
  if (message.role === "user") {
    return "用户";
  }

  if (message.role === "system") {
    return "系统";
  }

  return "轻灵厨房";
}

function MessageContent({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return <p className="message-bubble__plain-text">{message.content}</p>;
  }

  if (message.status === "streaming" && !message.content) {
    return <div className="message-bubble__streaming-cursor" aria-label="正在生成回复" />;
  }

  return (
    <div className="message-bubble__markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
      {message.status === "streaming" && (
        <span className="message-bubble__inline-cursor" aria-hidden="true" />
      )}
    </div>
  );
}

export function MessageList({ conversation }: MessageListProps) {
  const messageListRef = useRef<HTMLDivElement | null>(null);
  const [isBackToTopVisible, setIsBackToTopVisible] = useState(false);
  const lastMessage = conversation.messages[conversation.messages.length - 1];

  function updateBackToTopVisibility() {
    const messageListElement = messageListRef.current;
    setIsBackToTopVisible(Boolean(messageListElement && messageListElement.scrollTop > 48));
  }

  function scrollToTop() {
    messageListRef.current?.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  }

  useLayoutEffect(() => {
    const messageListElement = messageListRef.current;
    if (!messageListElement) {
      return;
    }

    messageListElement.scrollTop = messageListElement.scrollHeight;
    updateBackToTopVisibility();
  }, [conversation.id, lastMessage?.id]);

  return (
    <section className="message-panel">
      <div className="message-list" ref={messageListRef} onScroll={updateBackToTopVisibility}>
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

              {message.content && <MessageContent message={message} />}

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

      {isBackToTopVisible && (
        <button
          className="message-back-to-top"
          type="button"
          aria-label="回到顶部"
          title="回到顶部"
          onClick={scrollToTop}
        >
          ↑
        </button>
      )}
    </section>
  );
}
