/**
 * Playwright — Co-Director chat attachment vision + reference generation.
 * Reuses Korri Anadriya. Never creates a new project.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const EVIDENCE = path.join("docs", "architecture", "codirector", "evidence", "chat-vision");
const KNOWN_VENTURE_ASSET = "b98585a0-8829-48cc-8c7b-63b9687955bb";
const FIXTURE = path.join("tests", "e2e", "codirector", "fixtures", "vision-upload.png");
const LIVE =
  "I would like to see the created image more like what you see attached through GPT Image 2.";
const DENIAL =
  /cannot see the image|don't have access to file uploads|cannot access file uploads|text-only assistant|describe the image for me/i;

test.setTimeout(300_000);

async function streamChat(messages: { role: string; content: string }[], attachmentIds: string[]) {
  const res = await fetch(`${API}/api/codirector/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: PROJECT_ID,
      mode: "chat",
      request_id: `pw-vision-${Date.now()}`,
      messages,
      attachment_ids: attachmentIds,
    }),
  });
  expect(res.ok, `stream HTTP ${res.status}`).toBeTruthy();
  const text = await res.text();
  const events = text
    .split("\n")
    .filter((line) => line.startsWith("data: "))
    .map((line) => {
      try {
        return JSON.parse(line.slice(6));
      } catch {
        return null;
      }
    })
    .filter(Boolean) as Array<Record<string, unknown>>;
  const assistant = events
    .filter((ev) => ev.type === "assistant" || ev.type === "token" || ev.type === "execution_status")
    .map((ev) => String(ev.content || ""))
    .join("\n");
  return { events, assistant, raw: text };
}

async function resolveVentureAsset(): Promise<string> {
  if (KNOWN_VENTURE_ASSET) return KNOWN_VENTURE_ASSET;
  const listed = await fetch(`${API}/api/projects/${PROJECT_ID}/library`);
  if (listed.ok) {
    const body = (await listed.json()) as {
      assets?: Array<{ id: string; filename?: string; tag?: string; name?: string }>;
      items?: Array<{ id: string; filename?: string; tag?: string; name?: string }>;
    };
    const pool = [...(body.assets || []), ...(body.items || [])];
    const existing = pool.find((asset) =>
      /venture corridor scene/i.test(`${asset.filename || ""} ${asset.tag || ""} ${asset.name || ""}`),
    );
    if (existing?.id) return existing.id;
  }
  const bytes = fs.readFileSync(FIXTURE);
  const form = new FormData();
  form.append("file", new Blob([bytes], { type: "image/png" }), "Venture Corridor scene.png");
  form.append("kind", "image");
  form.append("tag", "Venture Corridor scene.png");
  const up = await fetch(`${API}/api/projects/${PROJECT_ID}/assets`, { method: "POST", body: form });
  expect(up.ok, `upload HTTP ${up.status}`).toBeTruthy();
  const created = (await up.json()) as { id?: string; assetId?: string };
  const id = created.id || created.assetId;
  expect(id).toBeTruthy();
  return String(id);
}

test("direct vision: what do you see does not deny uploads", async () => {
  fs.mkdirSync(EVIDENCE, { recursive: true });
  const assetId = await resolveVentureAsset();
  const { assistant, events } = await streamChat(
    [{ role: "user", content: "What do you see in this image?" }],
    [assetId],
  );
  fs.writeFileSync(path.join(EVIDENCE, "direct-vision.json"), JSON.stringify({ assistant, events }, null, 2));
  expect(assistant, assistant).not.toMatch(DENIAL);
  expect(assistant.length).toBeGreaterThan(20);
});

test("reference generation: attached image proceeds without interview", async () => {
  const assetId = await resolveVentureAsset();
  const { assistant, events } = await streamChat([{ role: "user", content: LIVE }], [assetId]);
  fs.writeFileSync(
    path.join(EVIDENCE, "reference-generation.json"),
    JSON.stringify({ assistant, events: events.map((ev) => ev.type) }, null, 2),
  );
  expect(assistant, assistant).not.toMatch(DENIAL);
  expect(assistant, assistant).not.toMatch(/what is the (lighting|art style)/i);
  const acted = events.some(
    (ev) => ev.type === "execution_status" || String(ev.capability || "") === "image.generate",
  );
  expect(acted || /generat/i.test(assistant)).toBeTruthy();
});
