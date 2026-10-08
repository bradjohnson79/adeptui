import { CHAT_MODEL } from "./types";

export type ChatMessage = { role: "user" | "assistant"; content: string };

export interface ChatModelProvider {
  readonly model: typeof CHAT_MODEL;
  stream(input: { instructions: string; messages: ChatMessage[]; signal: AbortSignal }): AsyncGenerator<string>;
}

type FetchLike = typeof fetch;

export function assertChatModel(value: string | undefined): typeof CHAT_MODEL {
  if (value && value !== CHAT_MODEL) {
    throw new Error("The configured chat model is not GPT-5 mini.");
  }
  return CHAT_MODEL;
}

export function createOpenAIProvider(env: { apiKey?: string; model?: string; fetchImpl?: FetchLike }): ChatModelProvider {
  const model = assertChatModel(env.model);
  const fetchImpl = env.fetchImpl ?? fetch;
  const apiKey = env.apiKey?.trim() ?? "";
  return {
    model,
    async *stream({ instructions, messages, signal }) {
      if (!apiKey) throw new Error("missing_credentials");
      const response = await fetchImpl("https://api.openai.com/v1/responses", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model,
          instructions,
          input: messages,
          stream: true,
          max_output_tokens: 800,
          text: { format: { type: "text" }, verbosity: "low" },
          reasoning: { effort: "low" },
        }),
        signal,
      });
      if (!response.ok || !response.body) throw new Error("provider_unavailable");
      yield* readResponseStream(response.body);
    },
  };
}

export async function* readResponseStream(body: ReadableStream<Uint8Array>): AsyncGenerator<string> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n");
    buffer = parts.pop() ?? "";
    for (const line of parts) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;
      const payload = trimmed.slice(5).trim();
      if (!payload || payload === "[DONE]") continue;
      let event: { type?: string; delta?: string; message?: string };
      try {
        event = JSON.parse(payload) as { type?: string; delta?: string; message?: string };
      } catch {
        continue;
      }
      if (event.type === "response.output_text.delta" && event.delta) yield event.delta;
      if (event.type === "error") throw new Error("provider_unavailable");
    }
  }
}
