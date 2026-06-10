import { router } from "expo-router";
import { ScrollView, Text, View } from "react-native";

import { PrimaryButton } from "@/components/ui/primary-button";
import { colors, spacing } from "@/constants/app-theme";
import { useAuth } from "@/features/auth/providers/auth-provider";

export default function SettingsRoute() {
  const { user, signOut } = useAuth();

  async function handleSignOut() {
    await signOut();
    router.replace("/(auth)/sign-in");
  }

  return (
    <ScrollView
      contentInsetAdjustmentBehavior="automatic"
      contentContainerStyle={{ gap: spacing.lg, padding: spacing.md }}
    >
      <View
        style={{
          backgroundColor: colors.surface,
          borderColor: colors.border,
          borderRadius: 18,
          borderWidth: 1,
          gap: spacing.sm,
          padding: spacing.md,
        }}
      >
        <Text selectable style={{ color: colors.text, fontSize: 20, fontWeight: "700" }}>
          {user?.username ?? "CookingAgent 用户"}
        </Text>
        <Text selectable style={{ color: colors.textMuted }}>
          {user?.email}
        </Text>
      </View>
      <PrimaryButton label="退出登录" onPress={() => void handleSignOut()} />
    </ScrollView>
  );
}
