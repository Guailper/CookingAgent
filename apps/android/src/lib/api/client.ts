import { fetch } from "expo/fetch";

import { tokenStorage } from "@/lib/auth/token-storage";
import type { ApiErrorPayload } from "@/types/api";

import { getApiBaseUrl } from "./config";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code = "UNKNOWN_ERROR",
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type ApiRequestOptions = RequestInit & {
  authenticated?: boolean;
};

export async function apiFetch(path: string, options: ApiRequestOptions = {}) {
  const { authenticated = true, headers, ...requestOptions } = options;
  const token = authenticated ? await tokenStorage.get() : null;

  return fetch(`${getApiBaseUrl()}${path}`, {
    ...requestOptions,
    headers: {
      ...(requestOptions.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...headers,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
}

export async function requestJson<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  let response: Response;

  try {
    response = await apiFetch(path, options);
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    throw new ApiError("Unable to connect to the CookingAgent backend.", 0, "NETWORK_ERROR");
  }

  const payload = (await response.json().catch(() => null)) as ApiErrorPayload | T | null;

  if (!response.ok) {
    const apiError = payload as ApiErrorPayload | null;
    throw new ApiError(
      apiError?.message ?? `Request failed (HTTP ${response.status}).`,
      response.status,
      apiError?.code,
    );
  }

  return payload as T;
}
