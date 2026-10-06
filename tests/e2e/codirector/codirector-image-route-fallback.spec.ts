/**
 * Co-Director hosted image fallback — PREFERRED fail-forward + STRICT block.
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
const RETRY_GPT_ONLY = "Retry with the same prompt and use GPT Image 2 only.";
const FORGOT = /didn't carry over|need the original prompt|paste the (?:original )?prompt/i;
const NO_PRIOR = /don't have a previous picture request/i;
const REFUSED = /i will not switch/i;
const STRICT_BLOCK = /only that model/i;

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

function jobIdsFrom(events: Record<string, any>[]): string[] {
  const ids: string[] = [];
  for (const evt of executionEvents(events)) {
    const exec = evt.execution || {};
    for (const id of exec.job_ids || exec.jobIds || []) {
      if (id) ids.push(String(id));
    }
    for (const child of exec.child_jobs || []) {
      if (child?.job_id) ids.push(String(child.job_id));
    }
  }
  return [...new Set(ids)];
}

test.describe("Co-Director image route fallback", () => {
  test("PREFERRED GPT Image 2 fail-forwards to a real job; STRICT blocks", async ({
    request,
    page,
  }) => {
    let preferred = await streamChatEvents(request, PROJECT_ID, RETRY_GPT);
    if (NO_PRIOR.test(preferred.assistantText)) {
      const first = await streamChatEvents(request, PROJECT_ID, VENTURE_BRIEF);
      expect(executionEvents(first.events).length, first.assistantText).toBeGreaterThan(0);
      preferred = await streamChatEvents(request, PROJECT_ID, RETRY_GPT);
    }
    expect(preferred.assistantText).not.toMatch(FORGOT);
    expect(preferred.assistantText).not.toMatch(REFUSED);
    const preferredJobs = jobIdsFrom(preferred.events);
    expect(preferredJobs.length, preferred.assistantText).toBeGreaterThan(0);

    const packs = await request.get(`${API}/api/codirector/projects/${PROJECT_ID}/executions`);
    expect(packs.ok()).toBeTruthy();
    const listed = await packs.json();
    const rows = listed.packs || listed.executions || listed.items || listed;
    const latest = Array.isArray(rows) ? rows[0] : null;
    const snap =
      latest?.plan_data?.canonicalGenerationRequest ||
      latest?.planData?.canonicalGenerationRequest ||
      latest?.canonicalGenerationRequest ||
      {};
    if (snap.lockLevel) {
      expect(snap.lockLevel).toBe("PREFERRED");
    }
    if (snap.fallbackAudit) {
      expect(snap.fallbackAudit.requestedModelId || snap.requestedModelId || "").toMatch(/gpt/i);
    }

    await page.goto(`/project/${PROJECT_ID}?workspace=codirector`);
    await page.reload();

    const strict = await streamChatEvents(request, PROJECT_ID, RETRY_GPT_ONLY);
    expect(strict.assistantText).not.toMatch(FORGOT);
    expect(jobIdsFrom(strict.events).length, strict.assistantText).toBe(0);
    const afterStrict = await request.get(`${API}/api/codirector/projects/${PROJECT_ID}/executions`);
    expect(afterStrict.ok()).toBeTruthy();
    const listedStrict = await afterStrict.json();
    const strictRows = listedStrict.executions || listedStrict.packs || listedStrict.items || [];
    const strictPack = Array.isArray(strictRows) ? strictRows[0] : null;
    const strictSnap = strictPack?.plan_data?.canonicalGenerationRequest || {};
    const strictText = [
      strict.assistantText,
      strictPack?.error,
      strictSnap?.fallbackAudit?.why,
    ]
      .filter(Boolean)
      .join(" ");
    expect(strictText, JSON.stringify({ id: strictPack?.execution_id, status: strictPack?.status })).toMatch(
      STRICT_BLOCK,
    );
    expect(strictSnap.lockLevel || "").toBe("STRICT");
    expect(strictSnap.jobIds || []).toEqual([]);
  });
});
