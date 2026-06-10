import { describe, expect, it } from "vitest";

import { resolveApiBaseUrl } from "../config";

describe("resolveApiBaseUrl", () => {
  it("removes trailing slashes from a configured HTTP URL", () => {
    expect(resolveApiBaseUrl("http://192.168.31.254:8000/api/v1/")).toBe(
      "http://192.168.31.254:8000/api/v1",
    );
  });

  it("rejects a missing API URL", () => {
    expect(() => resolveApiBaseUrl(undefined)).toThrow("EXPO_PUBLIC_API_URL");
  });

  it("rejects non-HTTP URLs", () => {
    expect(() => resolveApiBaseUrl("ftp://example.com/api/v1")).toThrow("HTTP");
  });
});
