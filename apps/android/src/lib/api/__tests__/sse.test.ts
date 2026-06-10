import { describe, expect, it } from "vitest";

import { parseServerSentEventBlock } from "../sse";

describe("parseServerSentEventBlock", () => {
  it("parses named events and joins multiline data", () => {
    expect(
      parseServerSentEventBlock('event: delta\ndata: {"content":"a"}\ndata: {"content":"b"}'),
    ).toEqual({
      eventName: "delta",
      dataText: '{"content":"a"}\n{"content":"b"}',
    });
  });

  it("uses message as the default event name", () => {
    expect(parseServerSentEventBlock("data: ready")).toEqual({
      eventName: "message",
      dataText: "ready",
    });
  });
});
