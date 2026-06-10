import { beforeEach, describe, expect, it } from "vitest";

import { tokenStorage } from "../token-storage.web";

const values = new Map<string, string>();

beforeEach(() => {
  values.clear();
  Object.defineProperty(globalThis, "sessionStorage", {
    configurable: true,
    value: {
      getItem: (key: string) => values.get(key) ?? null,
      removeItem: (key: string) => values.delete(key),
      setItem: (key: string, value: string) => values.set(key, value),
    },
  });
});

describe("web tokenStorage", () => {
  it("stores the access token for the current browser session", async () => {
    await tokenStorage.set("token-123");

    expect(await tokenStorage.get()).toBe("token-123");

    await tokenStorage.remove();
    expect(await tokenStorage.get()).toBeNull();
  });
});
