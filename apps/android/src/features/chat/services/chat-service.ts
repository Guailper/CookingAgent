import { apiFetch, requestJson } from "@/lib/api/client";
import { parseServerSentEventBlock } from "@/lib/api/sse";
import type { ApiEnvelope, ConversationItem, MessageItem } from "@/types/api";

export async function listConversations() {
  const response = await requestJson<ApiEnvelope<ConversationItem[]>>("/conversations");
  return response.data;
}

export async function createConversation(title = "新的美食灵感") {
  const response = await requestJson<ApiEnvelope<ConversationItem>>("/conversations", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
  return response.data;
}

export async function listMessages(conversationId: string) {
  const response = await requestJson<ApiEnvelope<MessageItem[]>>(
    `/conversations/${conversationId}/messages`,
  );
  return response.data;
}

export async function sendAgentMessageStream(
  conversationId: string,
  content: string,
  onDelta: (content: string) => void,
) {
  const response = await apiFetch("/agent/chat/stream", {
    method: "POST",
    body: JSON.stringify({
      conversation_id: conversationId,
      content: content.trim(),
      attachment_ids: [],
      extra_metadata: {
        client: "android",
      },
    }),
  });

  if (!response.ok) {
    throw new Error(`Unable to start agent stream (HTTP ${response.status}).`);
  }

  if (!response.body) {
    throw new Error("The backend did not return a readable stream.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let bufferedText = "";

  while (true) {
    const { value, done } = await reader.read();
    bufferedText += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const blocks = bufferedText.split(/\r?\n\r?\n/);
    bufferedText = blocks.pop() ?? "";

    for (const block of blocks) {
      const event = parseServerSentEventBlock(block);
      if (event.eventName !== "delta" || !event.dataText) continue;

      const payload = JSON.parse(event.dataText) as { content?: unknown };
      const delta = typeof payload.content === "string" ? payload.content : "";
      if (delta) onDelta(delta);
    }

    if (done) break;
  }
}
