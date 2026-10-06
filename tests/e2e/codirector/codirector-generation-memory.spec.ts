/**
 * Co-Director canonical generation memory — stream retry without repaste.
 * Reuses Korri Anadriya. Never POST /api/projects.
 */
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API } from "../helpers/app";

const PROJECT_ID =
  process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";

const VENTURE_BRIEF =
  "Create a Silver metallic Venture corridor scene where we see an elevator door " +
  "at the end of the corridor, and then about 10 meters ahead, there is a door " +
  "that leads to a Combat Chamber room. The corridor should like something you " +
  "would see through an underground research facility. Somewhat sci-fi futuristic, " +
  "full wide master shot. Please create this image for me now.";

const RETRY_GPT = "Retry with same prompt again and use GPT Image 2.";
const RETRY_FLUX = "Retry that with Flux.";
const FORGOT = /didn't carry over|need the original prompt|paste the (?:original )?prompt/i;
const NO_PRIOR = /don't have a previous picture request/i;

async function streamChatEvents(
  request: APIRequestContext,
  projectId: string,
  message: string,
  timeoutMs = 180_000,
): Promise<{ events: Record<string, any>[]; assistantText: string }> {
  const events: Record<string, any>[] = [];
  let assistantText = "";
  const res = await request.post(`${API}/api/codirector/chat/stream`, {
    data: {
      messages: [{ role: "user", content: message }],
      project_id: projectId,
      mode: "chat",
    },
    timeout: timeoutMs,
  });
  if (!res.ok()) {
    throw new Error(`chat stream failed: ${res.status()} ${await res.text()}`);
  }
  const text = (await res.body()).toString("utf8");
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("data:")) continue;
    const payload = trimmed.slice("data:".length).trim();
    if (!payload) continue;
    try {
      const evt = JSON.parse(payload);
      events.push(evt);
      if (evt.type === "completed" || evt.type === "completion") {
        assistantText = evt.content || assistantText;
      }
      if (evt.type === "delta" && evt.text) assistantText += evt.text;
      if (evt.type === "assistant" && evt.content) assistantText += evt.content;
    } catch {
      /* ignore */
    }
  }
  return { events, assistantText };
}

function executionEvents(events: Record<string, any>[]) {
  return events.filter((e) => e.type === "execution_status" || e.execution);
}

test.describe("Co-Director generation memory", () => {
  test("retry reuses stored Venture brief without asking to paste it", async ({
    request,
    page,
  }) => {
    let retry = await streamChatEvents(request, PROJECT_ID, RETRY_GPT);
    if (NO_PRIOR.test(retry.assistantText)) {
      const first = await streamChatEvents(request, PROJECT_ID, VENTURE_BRIEF);
      expect(executionEvents(first.events).length, first.assistantText).toBeGreaterThan(0);
      retry = await streamChatEvents(request, PROJECT_ID, RETRY_GPT);
    }
    expect(retry.assistantText).not.toMatch(FORGOT);
    const retryExec = executionEvents(retry.events);
    expect(retryExec.length, retry.assistantText).toBeGreaterThan(0);
    expect(retryExec[0]?.execution?.execution_id).toBeTruthy();

    await page.goto(`/project/${PROJECT_ID}?workspace=codirector`);
    await page.reload();
    const afterRefresh = await streamChatEvents(request, PROJECT_ID, RETRY_FLUX);
    expect(afterRefresh.assistantText).not.toMatch(FORGOT);
    const fluxExec = executionEvents(afterRefresh.events);
    expect(fluxExec.length, afterRefresh.assistantText).toBeGreaterThan(0);
    const jobs =
      fluxExec[0]?.execution?.job_ids ||
      fluxExec[0]?.execution?.jobIds ||
      (fluxExec[0]?.execution?.child_jobs || []).map((c: { job_id?: string }) => c.job_id);
    expect((jobs || []).filter(Boolean).length, afterRefresh.assistantText).toBeGreaterThan(0);
  });
});
