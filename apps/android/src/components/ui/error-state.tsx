import { Pressable, Text, View } from "react-native";

import { colors, spacing } from "@/constants/app-theme";

type ErrorStateProps = {
  message: string;
  onRetry?: () => void;
};

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <View style={{ alignItems: "center", gap: spacing.md, padding: spacing.lg }}>
      <Text selectable style={{ color: colors.danger, textAlign: "center" }}>
        {message}
      </Text>
      {onRetry ? (
        <Pressable
          onPress={onRetry}
          style={({ pressed }) => ({
            backgroundColor: pressed ? colors.primaryPressed : colors.primary,
            borderRadius: 999,
            paddingHorizontal: spacing.lg,
            paddingVertical: spacing.sm,
          })}
        >
          <Text style={{ color: "#FFFFFF", fontWeight: "700" }}>重试</Text>
        </Pressable>
      ) : null}
    </View>
  );
}
