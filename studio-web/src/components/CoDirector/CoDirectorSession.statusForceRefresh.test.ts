import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

/**
 * Guards the Co-Director 100% live-UI defect: the Status panel Re-check button
 * calls `runStatusCheck({ forceRefresh: true })`, but the session used to drop
 * `forceRefresh` from the request body. Combined with the 30s TTL in the status
 * client, the header chip / panel could show a stale Blocked 35 (comfy.health
 * offline) while the API latest run was 100. These source-level assertions keep
 * the wiring honest: forceRefresh reaches the backend body, and a successful
 * check invalidates + re-seeds the shared status cache so a later
 * openStatusPanel/loadStatus cannot overwrite the fresh run with a stale one.
 */
describe("CoDirectorSession runStatusCheck forceRefresh wiring", () => {
  const sessionSrc = readFileSync(new URL("./CoDirectorSession.tsx", import.meta.url), "utf8");
  const clientSrc = readFileSync(new URL("../../codirector/status/client.ts", import.meta.url), "utf8");

  it("types runStatusCheck opts with forceRefresh", () => {
    expect(sessionSrc).toContain(
      "runStatusCheck: (opts?: { deep?: boolean; forceRefresh?: boolean }) => Promise<void>;",
    );
  });

  it("implements runStatusCheck with a forceRefresh opt", () => {
    expect(sessionSrc).toContain("async (opts?: { deep?: boolean; forceRefresh?: boolean }) =>");
  });

  it("forwards forceRefresh into the request body sent to the backend", () => {
    // The body must carry forceRefresh so the backend runner bypasses its TTL
    // cache (runner._execute_one + run_status_check invalidate on force_refresh).
    expect(sessionSrc).toContain("forceRefresh: Boolean(opts?.forceRefresh)");
  });

  it("imports invalidateStatusCaches and rememberLatestStatus from the status client", () => {
    expect(sessionSrc).toContain("invalidateStatusCaches");
    expect(sessionSrc).toContain("rememberLatestStatus");
    // Both helpers must be exported by the client module.
    expect(clientSrc).toContain("export function invalidateStatusCaches");
    expect(clientSrc).toContain("export function rememberLatestStatus");
  });

  it("invalidates then re-seeds the shared status cache after a successful check", () => {
    // Order matters: invalidate clears the stale 30s-TTL entry, then
    // rememberLatestStatus seeds the fresh run so openStatusPanel/loadStatus
    // read it back instead of refetching a stale cached latest.
    const invalidateIdx = sessionSrc.indexOf("invalidateStatusCaches(uiContext.projectId, uiContext.sceneId)");
    const rememberIdx = sessionSrc.indexOf("rememberLatestStatus(uiContext.projectId, uiContext.sceneId, run)");
    expect(invalidateIdx).toBeGreaterThan(-1);
    expect(rememberIdx).toBeGreaterThan(-1);
    expect(rememberIdx).toBeGreaterThan(invalidateIdx);
  });

  it("does not silently drop forceRefresh or fabricate a fake 100", () => {
    // The panel still owns the 35/84/95 bands; the session must not hardcode a
    // score or hide a Blocked run. It only forwards the creator's re-check.
    expect(sessionSrc).not.toContain("score: 100");
    expect(sessionSrc).not.toContain("band: \"Operational\"");
  });
});
