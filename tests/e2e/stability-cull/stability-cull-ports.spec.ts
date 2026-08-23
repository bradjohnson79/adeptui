import { expect, test } from "@playwright/test";
import { creatorUiBase, studioApiBase } from "../setup/ownerProjectGuard";

test("creator UI is not retired :8760 and API healthz is :8758", async ({ request }) => {
  const ui = creatorUiBase();
  expect(ui).not.toContain(":8760");
  const api = studioApiBase();
  expect(api).toContain("8758");
  const health = await request.get(`${api}/api/healthz`);
  expect(health.status(), "Studio API healthz").toBe(200);
});
