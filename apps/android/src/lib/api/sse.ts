export type ServerSentEventBlock = {
  eventName: string;
  dataText: string;
};

export function parseServerSentEventBlock(block: string): ServerSentEventBlock {
  let eventName = "message";
  const dataLines: string[] = [];

  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    }

    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }

  return {
    eventName,
    dataText: dataLines.join("\n"),
  };
}
