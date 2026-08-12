import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { API } from "../../helpers/app";

export type ConversationAttachment = {
  assetId?: string;
  asset_id?: string;
  name?: string;
  mimeType?: string;
  mime_type?: string;
  kind?: string;
  source?: string;
};

export type ConversationMessage = {
  id?: string;
  role: string;
  content: string;
  created_at?: string;
  attachments?: ConversationAttachment[];
};

export const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

export const TINY_WAV = Buffer.from(
  "UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=",
  "base64",
);

export const TINY_MP4 = Buffer.from(
  "AAAAFGZ0eXBpc29tAAACAGlzb21pc28y",
  "base64",
);

export async function openCoDirectorFullScreen(page: Page, projectId: string) {
  await page.goto(`/co-director?projectId=${encodeURIComponent(projectId)}`);
  await expect(
    page.getByTestId("codirector-fullscreen-shell").or(page.getByTestId("codirector-workspace")).first(),
  ).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId("codirector-composer-input")).toBeVisible({ timeout: 30_000 });
}

export async function expectFixedViewportFraming(page: Page) {
  const metrics = await page.evaluate(() => {
    const shell = document.querySelector('[data-testid="codirector-fullscreen-shell"]') as HTMLElement | null;
    const rect = shell?.getBoundingClientRect();
    return {
      left: rect?.left ?? 0,
      right: rect ? window.innerWidth - rect.right : 0,
      width: rect?.width ?? 0,
      viewportWidth: window.innerWidth,
      scrollHeight: document.documentElement.scrollHeight,
      clientHeight: document.documentElement.clientHeight,
    };
  });
  expect(metrics.width / metrics.viewportWidth).toBeGreaterThanOrEqual(0.88);
  expect(metrics.width / metrics.viewportWidth).toBeLessThanOrEqual(0.92);
  expect(metrics.left / metrics.viewportWidth).toBeGreaterThanOrEqual(0.04);
  expect(metrics.right / metrics.viewportWidth).toBeGreaterThanOrEqual(0.04);
  expect(metrics.scrollHeight).toBeLessThanOrEqual(metrics.clientHeight + 2);
}

export async function sendChatTurn(page: Page, text: string) {
  const assistantBubbles = page.locator(".codirector-msg.assistant .codirector-msg-bubble");
  const assistantCountBefore = await assistantBubbles.count();
  await page.getByTestId("codirector-composer-input").fill(text);
  await page.getByRole("button", { name: "Send message" }).click();
  await expect
    .poll(async () => assistantBubbles.count(), { timeout: 120_000 })
    .toBeGreaterThan(assistantCountBefore);
  const lastAssistantBubble = assistantBubbles.last();
  await expect(lastAssistantBubble).toContainText(/\S/, { timeout: 20_000 });
  return (await lastAssistantBubble.innerText()).trim();
}

export async function getConversation(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/codirector/conversations/${projectId}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as { messages: ConversationMessage[] };
}

export async function uploadProjectAsset(
  request: APIRequestContext,
  projectId: string,
  opts: { name: string; mimeType: string; kind: string; buffer: Buffer; tag?: string },
) {
  const res = await request.post(`${API}/api/projects/${projectId}/assets`, {
    multipart: {
      file: {
        name: opts.name,
        mimeType: opts.mimeType,
        buffer: opts.buffer,
      },
      tag: opts.tag || opts.name,
      kind: opts.kind,
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as { id: string; tag?: string; filename?: string };
}
