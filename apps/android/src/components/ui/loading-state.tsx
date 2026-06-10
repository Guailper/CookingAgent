import { ActivityIndicator, View } from "react-native";

import { colors } from "@/constants/app-theme";

export function LoadingState() {
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
      <ActivityIndicator color={colors.primary} size="large" />
    </View>
  );
}
