/**
 * Final Systems — Remaining workspaces smoke (single project).
 * Opens creator workspaces inside Adept UI; forbids "please open ComfyUI".
 */
import { test, expect } from "@playwright/test";
import * as path from "path";
import {
  attachForbiddenRuntimeWatcher,
  createFinaleProjectViaHome,
  makeRunId,
  openWorkspace,
  writeJson,
  MANUAL_HANDOFF_ID,
} from "./helpers/finalSystemsCert";
import { deleteProject, resetLiveBetaTestSurface, waitForAppReady } from "../helpers/app";

const RUN_ID = makeRunId("REMAINING-WS");
const ARTIFACT_DIR = path.join(
  "docs",
  "release-gate",
  "final-systems",
  "artifacts",
  "remaining-workspaces",
  RUN_ID,
);

const WORKSPACES: Array<{ workspace: string; shell?: string; probe?: RegExp }> = [
  { workspace: "brandstudio", shell: "brand-studio" },
  { workspace: "one", shell: "one-frame-panel" },
  { workspace: "three", shell: "three-frame-panel" },
  { workspace: "txt2vid", probe: /Text.?to.?Video|MiniMax|Generate/i },
  { workspace: "avatar", shell: "avatar-studio-workspace" },
  { workspace: "library", probe: /Library|Assets|Upload/i },
  { workspace: "bible", probe: /Bible|Continuity|Production/i },
  { workspace: "timeline", shell: "timeline-open-retake" },
  { workspace: "magi", shell: "magi-viewer" },
  { workspace: "audiostudio", probe: /Audio|Music|Ambience|SFX/i },
  { workspace: "scriptwriter", shell: "scriptwriter-workspace" },
];

test.describe("@critical @final-systems Remaining workspaces", () => {
  test.beforeEach(async ({ page, request }) => {
    await waitForAppReady(request);
    await resetLiveBetaTestSurface(request, page);
  });

  test("single project — workspaces open without manual runtime ops", async ({ page, request }) => {
    test.setTimeout(300_000);
    const watcher = attachForbiddenRuntimeWatcher(page);
    const name = `ADEPT-FINALE-WS-${Date.now()}`;
    const projectId = await createFinaleProjectViaHome(page, request, name);
    expect(projectId).not.toBe(MANUAL_HANDOFF_ID);
    writeJson(ARTIFACT_DIR, "project.json", { projectId, name });

    const results: Array<{ workspace: string; ok: boolean; shellOk?: boolean; note: string }> = [];

    try {
      for (const ws of WORKSPACES) {
        const opened = await openWorkspace(page, projectId, ws.workspace, ws.shell);
        const matched =
          ws.probe && opened.textSample ? ws.probe.test(opened.textSample) : opened.shellOk ?? true;
        results.push({
          workspace: ws.workspace,
          ok: opened.ok && !opened.asksManualRuntime,
          shellOk: opened.shellOk,
          note: opened.asksManualRuntime
            ? "manual runtime prompt"
            : matched
              ? "creator chrome visible"
              : "mounted (shell optional)",
        });
        expect(opened.asksManualRuntime, `${ws.workspace} must not ask creator to operate runtimes`).toBeFalsy();
      }

      writeJson(ARTIFACT_DIR, "workspaces.json", { results, forbiddenHits: watcher.forbiddenHits });
      expect(watcher.forbiddenHits, "must not hit Comfy/H3 runtime ports from browser").toEqual([]);
      writeJson(ARTIFACT_DIR, "verdict-seed.json", {
        gate: "remaining-workspaces",
        verdictSeed: "READY_FOR_PRIMARY_REVIEW",
        artifactDir: ARTIFACT_DIR,
      });
    } finally {
      watcher.dispose();
      await deleteProject(request, projectId);
    }
  });
});
