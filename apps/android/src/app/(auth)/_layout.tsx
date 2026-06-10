import { Redirect, Stack } from "expo-router";

import { useAuth } from "@/features/auth/providers/auth-provider";

export default function AuthLayout() {
  const { status } = useAuth();

  if (status === "authenticated") {
    return <Redirect href="/(app)" />;
  }

  return <Stack screenOptions={{ headerShown: false }} />;
}
