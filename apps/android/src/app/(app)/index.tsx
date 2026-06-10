import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, router } from "expo-router";
import { FlatList, Pressable, Text, View } from "react-native";

import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { colors, spacing } from "@/constants/app-theme";
import { ConversationCard } from "@/features/chat/components/conversation-card";
import { createConversation, listConversations } from "@/features/chat/services/chat-service";

export default function ConversationsRoute() {
  const queryClient = useQueryClient();
  const conversations = useQuery({
    queryKey: ["conversations"],
    queryFn: listConversations,
  });
  const createConversationMutation = useMutation({
    mutationFn: () => createConversation(),
    onSuccess: async (conversation) => {
      await queryClient.invalidateQueries({ queryKey: ["conversations"] });
      router.push({
        pathname: "/chat/[conversationId]",
        params: { conversationId: conversation.public_id },
      });
    },
  });

  if (conversations.isLoading) return <LoadingState />;
  if (conversations.error) {
    return (
      <ErrorState
        message={conversations.error.message}
        onRetry={() => void conversations.refetch()}
      />
    );
  }

  return (
    <FlatList
      contentInsetAdjustmentBehavior="automatic"
      contentContainerStyle={{ gap: spacing.md, padding: spacing.md }}
      data={conversations.data ?? []}
      keyExtractor={(item) => item.public_id}
      ListHeaderComponent={
        <View style={{ gap: spacing.md }}>
          <View style={{ flexDirection: "row", gap: spacing.sm }}>
            <Pressable
              disabled={createConversationMutation.isPending}
              onPress={() => createConversationMutation.mutate()}
              style={({ pressed }) => ({
                backgroundColor: pressed ? colors.primaryPressed : colors.primary,
                borderRadius: 999,
                paddingHorizontal: spacing.md,
                paddingVertical: spacing.sm,
              })}
            >
              <Text style={{ color: "#FFFFFF", fontWeight: "700" }}>
                {createConversationMutation.isPending ? "创建中..." : "新建对话"}
              </Text>
            </Pressable>
            <Link href="/settings" asChild>
              <Pressable
                style={{
                  borderColor: colors.border,
                  borderRadius: 999,
                  borderWidth: 1,
                  paddingHorizontal: spacing.md,
                  paddingVertical: spacing.sm,
                }}
              >
                <Text style={{ color: colors.text }}>设置</Text>
              </Pressable>
            </Link>
          </View>
          {createConversationMutation.error ? (
            <Text selectable style={{ color: colors.danger }}>
              {createConversationMutation.error.message}
            </Text>
          ) : null}
        </View>
      }
      ListEmptyComponent={
        <Text selectable style={{ color: colors.textMuted, paddingVertical: spacing.xl }}>
          还没有会话，创建一个并开始询问今天的菜单。
        </Text>
      }
      renderItem={({ item }) => <ConversationCard conversation={item} />}
    />
  );
}
