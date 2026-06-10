export function resolveApiBaseUrl(rawUrl: string | undefined) {
  const value = rawUrl?.trim();

  if (!value) {
    throw new Error("EXPO_PUBLIC_API_URL is not configured.");
  }

  const url = new URL(value);
  if (!["http:", "https:"].includes(url.protocol)) {
    throw new Error("EXPO_PUBLIC_API_URL must use HTTP or HTTPS.");
  }

  return value.replace(/\/+$/, "");
}

export function getApiBaseUrl() {
  return resolveApiBaseUrl(process.env.EXPO_PUBLIC_API_URL);
}
