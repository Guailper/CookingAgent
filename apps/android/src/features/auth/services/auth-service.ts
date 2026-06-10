import { requestJson } from "@/lib/api/client";
import type { ApiEnvelope, AuthPayload, UserProfile } from "@/types/api";

export type PasswordLoginInput = {
  email: string;
  password: string;
};

export async function loginWithPassword(input: PasswordLoginInput) {
  const response = await requestJson<ApiEnvelope<AuthPayload>>("/auth/login", {
    authenticated: false,
    method: "POST",
    body: JSON.stringify(input),
  });

  return response.data;
}

export async function getCurrentUser() {
  const response = await requestJson<ApiEnvelope<UserProfile>>("/auth/me");
  return response.data;
}
