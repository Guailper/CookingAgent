import { router } from "expo-router";
import { useState } from "react";
import { ScrollView, Text, TextInput, View } from "react-native";

import { PrimaryButton } from "@/components/ui/primary-button";
import { colors, spacing } from "@/constants/app-theme";
import { useAuth } from "@/features/auth/providers/auth-provider";

export default function SignInRoute() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSignIn() {
    setError(null);
    setLoading(true);

    try {
      await signIn({ email: email.trim(), password });
      router.replace("/(app)");
    } catch (signInError) {
      setError(signInError instanceof Error ? signInError.message : "登录失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <ScrollView
      contentInsetAdjustmentBehavior="automatic"
      contentContainerStyle={{
        backgroundColor: colors.background,
        flexGrow: 1,
        justifyContent: "center",
        padding: spacing.lg,
      }}
      keyboardShouldPersistTaps="handled"
    >
      <View style={{ gap: spacing.lg }}>
        <View style={{ gap: spacing.sm }}>
          <Text selectable style={{ color: colors.primary, fontSize: 14, fontWeight: "800" }}>
            COOKING AGENT
          </Text>
          <Text selectable style={{ color: colors.text, fontSize: 34, fontWeight: "800" }}>
            今天想做点什么？
          </Text>
          <Text selectable style={{ color: colors.textMuted, fontSize: 16, lineHeight: 24 }}>
            登录后继续使用你的会话、菜谱知识库和长期偏好。
          </Text>
        </View>

        <View style={{ gap: spacing.md }}>
          <TextInput
            autoCapitalize="none"
            autoComplete="email"
            keyboardType="email-address"
            onChangeText={setEmail}
            placeholder="邮箱"
            placeholderTextColor={colors.textMuted}
            style={{
              backgroundColor: colors.surface,
              borderColor: colors.border,
              borderRadius: 14,
              borderWidth: 1,
              color: colors.text,
              minHeight: 52,
              paddingHorizontal: spacing.md,
            }}
            value={email}
          />
          <TextInput
            autoComplete="password"
            onChangeText={setPassword}
            placeholder="密码"
            placeholderTextColor={colors.textMuted}
            secureTextEntry
            style={{
              backgroundColor: colors.surface,
              borderColor: colors.border,
              borderRadius: 14,
              borderWidth: 1,
              color: colors.text,
              minHeight: 52,
              paddingHorizontal: spacing.md,
            }}
            value={password}
          />
          {error ? (
            <Text selectable style={{ color: colors.danger }}>
              {error}
            </Text>
          ) : null}
          <PrimaryButton
            disabled={!email.trim() || password.length < 6}
            label="登录"
            loading={loading}
            onPress={() => void handleSignIn()}
          />
        </View>
      </View>
    </ScrollView>
  );
}
