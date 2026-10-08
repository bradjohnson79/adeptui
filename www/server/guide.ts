import path from "node:path";
import { GUIDE_UNAVAILABLE } from "../src/guide/messages";
import { allowRequest, blockedIntent, cleanHistory, cleanMessage, cleanPage, refusalText } from "./guard";
import { buildKnowledge } from "./knowledge";
import { buildPrompt, toSources } from "./prompt";
import { createOpenAIProvider, type ChatModelProvider } from "./provider";
import { retrieve } from "./retrieve";
import type { GuideSource, StoredChunk } from "./types";

export type GuideBody = {
  message?: unknown;
  history?: unknown;
  page?: unknown;
};

export type GuideDeps = {
  chunks?: StoredChunk[];
  provider?: ChatModelProvider;
  now?: number;
  clientKey?: string;
};

let cached: StoredChunk[] | null = null;

export function knowledgeCache(docsRoot = path.join(process.cwd(), "docs")): StoredChunk[] {
  if (!cached) cached = buildKnowledge(docsRoot);
  return cached;
}

export function resetKnowledgeCache(): void {
  cached = null;
}

function sse(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

function streamText(parts: string[]): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder();
      for (const part of parts) controller.enqueue(encoder.encode(part));
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

function logGuide(event: string, fields: Record<string, string | number | boolean>): void {
  console.info(JSON.stringify({ guide: event, ...fields }));
}

export async function handleGuide(body: GuideBody, deps: GuideDeps = {}): Promise<Response> {
  const started = Date.now();
  const message = cleanMessage(body.message);
  if (!message) {
    logGuide("rejected", { reason: "size", ms: Date.now() - started });
    return new Response(JSON.stringify({ message: "Send a shorter question about Adept UI." }), {
      status: 400,
      headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
    });
  }
  const clientKey = deps.clientKey ?? "local";
  if (!allowRequest(clientKey, deps.now)) {
    logGuide("rate_limited", { ms: Date.now() - started });
    return streamText([sse("error", { message: "The guide is receiving too many questions. Please wait a few minutes, or search the documentation." })]);
  }
  if (blockedIntent(message)) {
    logGuide("refused", { ms: Date.now() - started });
    return streamText([sse("delta", { text: refusalText() }), sse("done", {})]);
  }
  const page = cleanPage(body.page);
  const history = cleanHistory(body.history);
  const chunks = deps.chunks ?? knowledgeCache();
  const hits = retrieve(message, chunks, page);
  const sources: GuideSource[] = toSources(hits);
  const prompt = buildPrompt({ question: message, history, hits, page });
  const provider =
    deps.provider ??
    createOpenAIProvider({
      apiKey: process.env.OPENAI_API_KEY,
      model: process.env.CHAT_MODEL,
    });
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      controller.enqueue(encoder.encode(sse("sources", { sources })));
      const abort = new AbortController();
      const timer = setTimeout(() => abort.abort(), 25000);
      let produced = false;
      try {
        for await (const text of provider.stream({ instructions: prompt.instructions, messages: prompt.input, signal: abort.signal })) {
          if (!text) continue;
          produced = true;
          controller.enqueue(encoder.encode(sse("delta", { text })));
        }
        if (!produced) throw new Error("empty");
        logGuide("ok", { ms: Date.now() - started, sources: sources.length, retrieval: hits.length > 0 });
        controller.enqueue(encoder.encode(sse("done", {})));
      } catch {
        logGuide("provider_error", { ms: Date.now() - started, retrieval: hits.length > 0 });
        if (!produced) controller.enqueue(encoder.encode(sse("error", { message: GUIDE_UNAVAILABLE })));
        else controller.enqueue(encoder.encode(sse("done", {})));
      } finally {
        clearTimeout(timer);
        controller.close();
      }
    },
  });
  return new Response(stream, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}
