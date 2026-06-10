import { ActivityIndicator, Pressable, Text } from "react-native";

import { colors, spacing } from "@/constants/app-theme";

type PrimaryButtonProps = {
  label: string;
  loading?: boolean;
  disabled?: boolean;
  onPress: () => void;
};

export function PrimaryButton({ label, loading = false, disabled = false, onPress }: PrimaryButtonProps) {
  return (
    <Pressable
      disabled={disabled || loading}
      onPress={onPress}
      style={({ pressed }) => ({
        alignItems: "center",
        backgroundColor:
          disabled || loading ? colors.border : pressed ? colors.primaryPressed : colors.primary,
        borderRadius: 14,
        minHeight: 50,
        justifyContent: "center",
        paddingHorizontal: spacing.md,
      })}
    >
      {loading ? (
        <ActivityIndicator color="#FFFFFF" />
      ) : (
        <Text style={{ color: "#FFFFFF", fontSize: 16, fontWeight: "700" }}>{label}</Text>
      )}
    </Pressable>
  );
}
