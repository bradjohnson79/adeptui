/**
 * Always-on Timeline Preflight (item 1) — signature + single-flight laws.
 *
 * The hook itself needs a DOM renderer (not installed here), so these tests
 * pin the two pure exported functions and source-assert the behavioral laws:
 * event-driven only (no polling), debounced, single-flight with trailing
 * rerun, stale-token guard.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  buildPreflightSignature,
  summarizePreflightFindings,
} from "./useTimelinePreflight";

const src = readFileSync(resolve(__dirname, "useTimelinePreflight.ts"), "utf8");

function masterWith(batch: Record<string, unknown>) {
  return { batchBlocks: [{ id: "b1", ...batch }] } as never;
}

describe("buildPreflightSignature", () => {
  it("is stable for identical input", () => {
    const m = masterWith({ generatorId: "minimax-h3", duration: { plannedDuration: 15 } });
    expect(buildPreflightSignature(m, null)).toBe(buildPreflightSignature(m, null));
  });

  it("changes when a preflight-relevant field changes", () => {
    const base = masterWith({
      generatorId: "minimax-h3",
      duration: { plannedDuration: 15 },
      promptSegments: [{ start: 0, length: 15, text: "a", role: "action", referenceBindingIds: [] }],
      references: [],
      sourceAnchors: [],
    });
    const sig = buildPreflightSignature(base, null);
    const variants: Array<Record<string, unknown>> = [
      { generatorId: "ltx-2.5-distilled" },
      { duration: { plannedDuration: 8 } },
      {
        promptSegments: [{ start: 0, length: 15, text: "b", role: "action", referenceBindingIds: [] }],
      },
      { references: [{ assetId: "asset_1", required: true, role: "identity" }] },
      { sourceAnchors: [{ kind: "end_frame" }] },
      { h3Resolution: { mode: "manual", megapixels: 1.0 } },
    ];
    for (const patch of variants) {
      const changed = masterWith({
        generatorId: "minimax-h3",
        duration: { plannedDuration: 15 },
        promptSegments: [{ start: 0, length: 15, text: "a", role: "action", referenceBindingIds: [] }],
        references: [],
        sourceAnchors: [],
        ...patch,
      });
      expect(buildPreflightSignature(changed, null)).not.toBe(sig);
    }
  });

  it("changes on master-level generator fields", () => {
    const m = masterWith({ generatorId: "minimax-h3" });
    const sig = buildPreflightSignature(m, null);
    expect(
      buildPreflightSignature({ batchBlocks: [], sceneGeneratorId: "minimax-h3" } as never, null),
    ).not.toBe(sig);
    expect(
      buildPreflightSignature({ batchBlocks: [], turboLora: true } as never, null),
    ).not.toBe(sig);
  });

  it("changes when H3 resolution changes", () => {
    const base = masterWith({ generatorId: "minimax-h3" });
    const sig = buildPreflightSignature(base, null);
    const changed = masterWith({
      generatorId: "minimax-h3",
      h3Resolution: { mode: "manual", megapixels: 1.0 },
    });
    expect(buildPreflightSignature(changed, null)).not.toBe(sig);
  });
});

describe("summarizePreflightFindings", () => {
  it("empty findings -> Ready, zero blocking", () => {
    expect(summarizePreflightFindings([])).toEqual({
      blockingCount: 0,
      summary: "Ready",
      status: "ready",
    });
  });

  it("error severity blocks; warning stays advisory", () => {
    const out = summarizePreflightFindings([
      { severity: "error", message: "no references", code: "MISSING_REFERENCES" },
      { severity: "warning", message: "long segment" },
    ]);
    expect(out.status).toBe("blocked");
    expect(out.blockingCount).toBe(1);
    expect(out.summary).toContain("MISSING_REFERENCES");
    expect(out.summary).toContain("1 advisory");
    expect(out.summary).not.toContain("additional info");
  });

  it("info notes are additional info, not advisories", () => {
    const out = summarizePreflightFindings([
      { severity: "info", message: "MiniMax H3 canvas: 1376×768 (1.0 MP · Manual)", code: "h3_canvas" },
      { severity: "info", message: "MiniMax H3 canvas: 1376×768 (1.0 MP · Manual)", code: "h3_canvas" },
      { severity: "info", message: "MiniMax H3 canvas: 1376×768 (1.0 MP · Manual)", code: "h3_canvas" },
    ]);
    expect(out.status).toBe("ready");
    expect(out.blockingCount).toBe(0);
    expect(out.summary).toBe("Ready with 3 additional info");
  });
});

describe("useTimelinePreflight behavioral laws (source assertions)", () => {
  it("is event-driven — no polling anywhere", () => {
    expect(src).not.toMatch(/setInterval/);
  });

  it("debounces signature changes (default 400ms)", () => {
    expect(src).toMatch(/opts\.debounceMs \?\? 400/);
    expect(src).toMatch(/setTimeout\(/);
  });

  it("is single-flight with a trailing rerun", () => {
    expect(src).toMatch(/inFlightRef\.current/);
    expect(src).toMatch(/pendingRef\.current = true/);
  });

  it("guards against stale responses by token", () => {
    expect(src).toMatch(/token !== tokenRef\.current/);
  });

  it("fails open — a preflight error never blocks Generate by itself", () => {
    expect(src).toMatch(/setStatus\("error"\)/);
  });
});
