import { Redirect } from "expo-router";

import { LoadingState } from "@/components/ui/loading-state";
import { useAuth } from "@/features/auth/providers/auth-provider";

export default function IndexRoute() {
  const { status } = useAuth();

  if (status === "loading") {
    return <LoadingState />;
  }

  return <Redirect href={status === "authenticated" ? "/(app)" : "/(auth)/sign-in"} />;
}
