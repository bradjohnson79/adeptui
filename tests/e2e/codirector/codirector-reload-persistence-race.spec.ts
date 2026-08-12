import { expect, type APIRequestContext, test } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { getConversation, openCoDirectorFullScreen, sendChatTurn } from "./helpers/audit";

/**
 * Regression test for the Co-Director conversation persistence race that
 * intermittently failed graduation Phase 15-18 ("conversation messages >= 3,
 * received 2" after reload).
 *
 * Root cause: `persistConversation` only merged the incoming messages onto the
 * latest server conversation when `conversationHydratedRef` was false. A turn
 * fires multiple persists (the fire-and-forget user-turn persist from `send()`,
 * then the final transcript persist from `performSend` completion / error /
 * cancel paths). The first persist set `conversationHydratedRef = true`, so the
 * second persist skipped the merge and saved a stale `[WELCOME, userMsg,
 * assistant?]` stub captured from the React `messages` closure at send time —
 * overwriting the real server conversation (the server save endpoint is a
 * full replace, not a merge) and truncating it to 2-3 messages.
 *
 * This test forces the race window deterministically: seed the server with a
 * multi-message history BEFORE the page loads, then send a turn before the
 * async conversation load completes (the `messages` closure is still
 * `[WELCOME]`). The fix (always merge by id onto the latest server state) must
 * preserve the seeded history; the buggy code would truncate it to the stub.
 */
test.describe("@critical @isolated codirector reload persistence race", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  async function seedConversation(
    request: APIRequestContext,
    projectId: string,
    messages: { id: string; role: string; content: string; created_at: string }[],
  ) {
    const res = await request.post(`${API}/api/codirector/conversations/${projectId}`, {
      data: { messages, model: null, provider_id: null },
    });
    expect(res.ok(), await res.text()).toBeTruthy();
  }

  test("send before async load completes never truncates server conversation on reload", async ({
    page,
    request,
  }) => {
    const project = await createTempProject(request, `CoDir Reload Race ${Date.now()}`);
    const now = Date.now();
    const seeded = [
      {
        id: `seed-u1-${now}`,
        role: "user",
        content: "We are making a short scene at Luma Coffee with Daniel and Maya.",
        created_at: new Date(now - 60000).toISOString(),
      },
      {
        id: `seed-a1-${now}`,
        role: "assistant",
        content: "Got it — Luma Coffee, two characters, short scene. Where should we start?",
        created_at: new Date(now - 59000).toISOString(),
      },
      {
        id: `seed-u2-${now}`,
        role: "user",
        content: "Start with the opening beat: Maya asks Daniel for one more cup.",
        created_at: new Date(now - 58000).toISOString(),
      },
      {
        id: `seed-a2-${now}`,
        role: "assistant",
        content: "Opening beat drafted. Want me to refine the dialogue or move to staging?",
        created_at: new Date(now - 57000).toISOString(),
      },
    ];

    try {
      // Seed the server with a 4-message history BEFORE the page loads so the
      // async conversation load has real data to hydrate, and a send that
      // races the load will capture a stale [WELCOME] closure.
      await seedConversation(request, project.id, seeded);

      // Open Co-Director fullscreen. The load effect starts an async GET here.
      await openCoDirectorFullScreen(page, project.id);

      // Immediately send a turn — before the async GET completes — to force
      // the race where the `messages` closure is still [WELCOME_ASSISTANT].
      // `sendChatTurn` waits for the assistant reply, so by the time it returns
      // both the fire-and-forget user-turn persist and the final transcript
      // persist have run.
      const raceReply = await sendChatTurn(page, "Add a closing beat where Daniel smiles.");
      expect(raceReply.length).toBeGreaterThan(0);

      // The turn's persists are serialized via a promise chain and the final
      // transcript persist may still be in flight when `sendChatTurn` returns
      // (it returns once the assistant bubble renders, which can precede the
      // save). Poll the server until it reflects the new turn — this is the
      // durable assertion (no fixed sleep).
      await expect
        .poll(
          async () => {
            const convo = await getConversation(request, project.id);
            return convo.messages.length;
          },
          { timeout: 30_000 },
        )
        .toBeGreaterThanOrEqual(seeded.length + 1);

      // The server conversation must never be truncated to the 2-3 message
      // stub. It must contain at least the seeded history (4) plus the new
      // user turn. This is the assertion that failed in graduation Phase 17
      // before the fix.
      const beforeReloadCheck = await getConversation(request, project.id);
      expect(beforeReloadCheck.messages.length).toBeGreaterThanOrEqual(seeded.length + 1);
      // Seeded messages must survive (not overwritten by the stub).
      for (const seed of seeded) {
        expect(
          beforeReloadCheck.messages.some((m) => m.id === seed.id),
          `seeded ${seed.id} (${seed.role}) must survive the race persist`,
        ).toBeTruthy();
      }
      // The new user turn must actually be persisted (sanity: the send really
      // happened and was not truncated away).
      expect(
        beforeReloadCheck.messages.some(
          (m) => m.role === "user" && m.content.includes("closing beat where Daniel smiles"),
        ),
        "new user turn must be persisted",
      ).toBeTruthy();

      // Reload and re-assert: the server conversation must survive the reload
      // with the full history intact (the original Phase 17 graduation gate).
      await page.reload();
      await expect(page.getByTestId("codirector-composer-input")).toBeVisible({ timeout: 30_000 });

      await expect
        .poll(
          async () => {
            const convo = await getConversation(request, project.id);
            return convo.messages.length;
          },
          { timeout: 30_000 },
        )
        .toBeGreaterThanOrEqual(seeded.length + 1);

      const afterReload = await getConversation(request, project.id);
      expect(afterReload.messages.length).toBeGreaterThanOrEqual(seeded.length + 1);
      for (const seed of seeded) {
        expect(
          afterReload.messages.some((m) => m.id === seed.id),
          `seeded ${seed.id} (${seed.role}) must survive reload`,
        ).toBeTruthy();
      }
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
