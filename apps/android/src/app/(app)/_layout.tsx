import { Redirect, Stack } from "expo-router";

import { LoadingState } from "@/components/ui/loading-state";
import { colors } from "@/constants/app-theme";
import { useAuth } from "@/features/auth/providers/auth-provider";

export default function AppLayout() {
  const { status } = useAuth();

  if (status === "loading") return <LoadingState />;
  if (status === "guest") return <Redirect href="/(auth)/sign-in" />;

  return (
    <Stack
      screenOptions={{
        contentStyle: { backgroundColor: colors.background },
        headerShadowVisible: false,
      }}
    >
      <Stack.Screen name="index" options={{ title: "CookingAgent" }} />
      <Stack.Screen name="chat/[conversationId]" options={{ title: "对话" }} />
      <Stack.Screen name="settings" options={{ title: "设置" }} />
    </Stack>
  );
}
