import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocalSearchParams } from "expo-router";
import { useState } from "react";
import {
  FlatList,
  KeyboardAvoidingView,
  Pressable,
  Text,
  TextInput,
  View,
} from "react-native";

import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { colors, spacing } from "@/constants/app-theme";
import { listMessages, sendAgentMessageStream } from "@/features/chat/services/chat-service";
import type { MessageItem } from "@/types/api";

function MessageBubble({ message }: { message: MessageItem }) {
  const isAssistant = message.role === "assistant";

  return (
    <View
      style={{
        alignSelf: isAssistant ? "stretch" : "flex-end",
        backgroundColor: isAssistant ? colors.surface : colors.primary,
        borderColor: isAssistant ? colors.border : colors.primary,
        borderRadius: 18,
        borderWidth: 1,
        maxWidth: isAssistant ? "100%" : "85%",
        padding: spacing.md,
      }}
    >
      <Text
        selectable
        style={{ color: isAssistant ? colors.text : "#FFFFFF", fontSize: 16, lineHeight: 24 }}
      >
        {message.content}
      </Text>
    </View>
  );
}

export default function ChatRoute() {
  const { conversationId } = useLocalSearchParams<{ conversationId: string }>();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [streamedReply, setStreamedReply] = useState("");

  const messages = useQuery({
    enabled: Boolean(conversationId),
    queryKey: ["messages", conversationId],
    queryFn: () => listMessages(conversationId),
  });

  const sendMessage = useMutation({
    mutationFn: async (content: string) => {
      setStreamedReply("");
      await sendAgentMessageStream(conversationId, content, (delta) => {
        setStreamedReply((current) => current + delta);
      });
    },
    onSuccess: async () => {
      setDraft("");
      setStreamedReply("");
      await queryClient.invalidateQueries({ queryKey: ["messages", conversationId] });
      await queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  if (messages.isLoading) return <LoadingState />;
  if (messages.error) {
    return <ErrorState message={messages.error.message} onRetry={() => void messages.refetch()} />;
  }

  const streamedMessage: MessageItem | null = streamedReply
    ? {
        public_id: "streaming-message",
        role: "assistant",
        content: streamedReply,
        status: "streaming",
        message_type: "text",
        created_at: new Date().toISOString(),
      }
    : null;

  return (
    <KeyboardAvoidingView
      behavior={process.env.EXPO_OS === "ios" ? "padding" : undefined}
      style={{ flex: 1 }}
    >
      <FlatList
        contentInsetAdjustmentBehavior="automatic"
        contentContainerStyle={{ gap: spacing.md, padding: spacing.md }}
        data={messages.data ?? []}
        keyExtractor={(item) => item.public_id}
        ListEmptyComponent={
          <Text selectable style={{ color: colors.textMuted }}>
            输入问题开始对话，例如：“冰箱里有鸡蛋和番茄，今晚做什么？”
          </Text>
        }
        ListFooterComponent={
          <View style={{ gap: spacing.sm }}>
            {streamedMessage ? <MessageBubble message={streamedMessage} /> : null}
            {sendMessage.error ? (
              <Text selectable style={{ color: colors.danger }}>
                {sendMessage.error.message}
              </Text>
            ) : null}
          </View>
        }
        renderItem={({ item }) => <MessageBubble message={item} />}
      />
      <View
        style={{
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          borderTopWidth: 1,
          flexDirection: "row",
          gap: spacing.sm,
          padding: spacing.md,
        }}
      >
        <TextInput
          editable={!sendMessage.isPending}
          multiline
          onChangeText={setDraft}
          placeholder="询问菜谱、食材或烹饪技巧"
          placeholderTextColor={colors.textMuted}
          style={{
            backgroundColor: colors.surfaceMuted,
            borderRadius: 18,
            color: colors.text,
            flex: 1,
            maxHeight: 120,
            minHeight: 46,
            paddingHorizontal: spacing.md,
            paddingVertical: spacing.sm,
          }}
          value={draft}
        />
        <Pressable
          disabled={!draft.trim() || sendMessage.isPending}
          onPress={() => sendMessage.mutate(draft.trim())}
          style={({ pressed }) => ({
            alignItems: "center",
            alignSelf: "flex-end",
            backgroundColor:
              !draft.trim() || sendMessage.isPending
                ? colors.border
                : pressed
                  ? colors.primaryPressed
                  : colors.primary,
            borderRadius: 999,
            height: 46,
            justifyContent: "center",
            width: 64,
          })}
        >
          <Text style={{ color: "#FFFFFF", fontWeight: "700" }}>
            {sendMessage.isPending ? "..." : "发送"}
          </Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}
