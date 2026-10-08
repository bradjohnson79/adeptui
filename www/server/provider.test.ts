import { describe, expect, it } from "vitest";
import { CHAT_MODEL } from "./types";
import { assertChatModel, createOpenAIProvider, readResponseStream } from "./provider";

describe("GPT-5 mini provider", () => {
  it("refuses to substitute another model", () => {
    expect(assertChatModel(undefined)).toBe(CHAT_MODEL);
    expect(assertChatModel("gpt-5-mini")).toBe("gpt-5-mini");
    expect(() => assertChatModel("gpt-4o-mini")).toThrow(/GPT-5 mini/);
  });

  it("streams text deltas from the Responses API", async () => {
    const calls: { url: string; body: { model: string } }[] = [];
    const payload = [
      'data: {"type":"response.output_text.delta","delta":"Timeline "}\n',
      'data: {"type":"response.output_text.delta","delta":"sequences shots."}\n',
      "data: [DONE]\n",
    ].join("\n");
    const provider = createOpenAIProvider({
      apiKey: "test-key",
      fetchImpl: async (url, init) => {
        calls.push({ url: String(url), body: JSON.parse(String(init?.body)) as { model: string } });
        return new Response(payload, { status: 200 });
      },
    });
    const text = [];
    for await (const delta of provider.stream({
      instructions: "Be brief.",
      messages: [{ role: "user", content: "What is Timeline?" }],
      signal: new AbortController().signal,
    })) {
      text.push(delta);
    }
    expect(calls[0]?.url).toBe("https://api.openai.com/v1/responses");
    expect(calls[0]?.body.model).toBe("gpt-5-mini");
    expect(text.join("")).toBe("Timeline sequences shots.");
    expect(JSON.stringify(calls[0]?.body)).not.toContain("test-key");
  });

  it("does not call the API without a key", async () => {
    const provider = createOpenAIProvider({ apiKey: "" });
    await expect(
      provider
        .stream({ instructions: "x", messages: [{ role: "user", content: "Hi" }], signal: new AbortController().signal })
        .next(),
    ).rejects.toThrow(/missing_credentials/);
  });
});

describe("response stream parser", () => {
  it("ignores non-text events", async () => {
    const raw = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          new TextEncoder().encode('data: {"type":"response.created"}\ndata: {"type":"response.output_text.delta","delta":"Hi"}\n'),
        );
        controller.close();
      },
    });
    const parts = [];
    for await (const part of readResponseStream(raw)) parts.push(part);
    expect(parts).toEqual(["Hi"]);
  });
});
