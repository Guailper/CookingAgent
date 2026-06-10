import { Link } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { colors, spacing } from "@/constants/app-theme";
import type { ConversationItem } from "@/types/api";

export function ConversationCard({ conversation }: { conversation: ConversationItem }) {
  return (
    <Link
      href={{
        pathname: "/chat/[conversationId]",
        params: { conversationId: conversation.public_id },
      }}
      asChild
    >
      <Pressable
        style={({ pressed }) => ({
          backgroundColor: pressed ? colors.surfaceMuted : colors.surface,
          borderColor: colors.border,
          borderRadius: 18,
          borderWidth: 1,
          padding: spacing.md,
        })}
      >
        <View style={{ gap: spacing.xs }}>
          <Text selectable style={{ color: colors.text, fontSize: 17, fontWeight: "700" }}>
            {conversation.title}
          </Text>
          <Text selectable style={{ color: colors.textMuted }}>
            {conversation.latest_message_at
              ? new Date(conversation.latest_message_at).toLocaleString("zh-CN")
              : "尚未发送消息"}
          </Text>
        </View>
      </Pressable>
    </Link>
  );
}
