import { describe, expect, it } from "vitest";
import type { SystemRow } from "./startupSnapshot";
import {
  buildStartupBoard,
  describeFinalStatus,
  duplicateLabels,
  type BootCheckView,
} from "./startupDisplay";

function row(id: string, label: string, state: SystemRow["state"], required = false): SystemRow {
  return { id, label, state, required };
}

const SNAPSHOT: SystemRow[] = [
  row("adept_core", "Adept Core", "online", true),
  row("studio_api", "Studio API", "online", true),
  row("creator_engine", "Creator Engine", "online", true),
  row("codirector", "Co-Director Runtime", "online"),
  row("local_ai", "Local AI Runtime", "online", true),
  row("comfy_mcp", "Comfy MCP", "online"),
  row("video_runtime", "Video Runtime", "on_demand"),
  row("remote_access", "Remote Access", "on_demand"),
];

function check(
  id: string,
  system: string,
  result: string,
  required = true,
  detail = "ok",
): BootCheckView {
  return { id, system, check: id, result, detail, required };
}

const STUDIO_API = [
  check("studio_api_process", "Studio API", "PASS"),
  check("studio_api_owner", "Studio API", "PASS"),
  check("studio_api_health", "Studio API", "PASS"),
  check("duplicate_api", "Studio API", "PASS"),
];

const CREATOR_UI = [
  check("vite_process", "Creator UI", "PASS", false),
  check("vite_health", "Creator UI", "PASS", false),
  check("duplicate_vite", "Creator UI", "PASS", false),
];

describe("startup display truth table", () => {
  it("collapses repeated owners into one label", () => {
    const board = buildStartupBoard(SNAPSHOT, [
      ...STUDIO_API,
      ...CREATOR_UI,
      check("codirector", "Co-Director", "PASS"),
      check("comfy", "Creator Engine", "PASS", false),
    ]);
    expect(duplicateLabels(board)).toEqual([]);
    const labels = board.flatMap((section) => section.rows.map((item) => item.label));
    expect(labels.filter((label) => label === "Studio API")).toHaveLength(1);
    expect(labels.filter((label) => label === "Creator UI")).toHaveLength(1);
    expect(labels.filter((label) => label === "Co-Director Runtime")).toHaveLength(1);
    expect(labels).not.toContain("Co-Director");
    expect(board.find((section) => section.id === "core")?.title).toBe("Core Runtime");
    expect(board.find((section) => section.id === "optional")?.rows.map((item) => item.label)).toEqual(
      expect.arrayContaining(["Video Runtime", "Remote Access"]),
    );
  });

  it("keeps Cloud 1.2 out of the board even if a stale payload includes it", () => {
    const board = buildStartupBoard(SNAPSHOT, [
      check("cloud_12", "Cloud 1.2", "OPTIONAL", false, "Cloud 1.2 is not part of this startup."),
      check("timeline", "Timeline", "PASS"),
    ]);
    const labels = board.flatMap((section) => section.rows.map((item) => item.label));
    expect(labels).not.toContain("Cloud 1.2");
    expect(duplicateLabels(board)).toEqual([]);
  });

  it("all required ready and optional setup missing stays GO without calling them essentials", () => {
    const status = describeFinalStatus({
      verdict: "GO",
      progressPct: 100,
      failed: [],
      setupOptional: [{ name: "Video Runtime" }, { name: "Local voice model" }],
      allRequiredOnline: true,
    });
    expect(status.headline).toBe("ADEPT UI READY — GO");
    expect(status.message).toBe("ALL REQUIRED SYSTEMS ONLINE");
    expect(status.body).toBe("All required systems are ready.");
    expect(status.progressLabel).toBe("Startup Complete");
    expect(status.phaseTitle).toBe("Adept UI Ready");
    expect(status.itemKind).toBe("optional");
    expect(status.items).toEqual(["Video Runtime", "Local voice model"]);
    expect(status.optionalNote).toMatch(/Optional components can be configured from Setup/);
    expect(JSON.stringify(status)).not.toMatch(/essentials are still missing/i);
    expect(status.contradiction).toBe(false);
  });

  it("a required miss withholds GO and names the requirement", () => {
    const status = describeFinalStatus({
      verdict: "NO-GO",
      progressPct: 80,
      failed: [{ system: "Timeline", check: "reference contract", detail: "1376x768 refused", result: "FAIL" }],
      setupOptional: [{ name: "Video Runtime" }],
      allRequiredOnline: true,
    });
    expect(status.headline).toBe("ADEPT UI SETUP REQUIRED");
    expect(status.message).not.toMatch(/ALL SYSTEMS ONLINE/);
    expect(status.body).toBe("1 required component needs attention.");
    expect(status.items).toEqual(["Timeline: 1376x768 refused"]);
    expect(status.itemKind).toBe("required");
    expect(status.contradiction).toBe(false);
  });

  it("a required failure stays NO-GO and visible", () => {
    const board = buildStartupBoard(SNAPSHOT, [check("library", "Library", "FAIL", true, "library unavailable")]);
    const library = board.flatMap((section) => section.rows).find((item) => item.label === "Library");
    expect(library?.badge).toBe("FAILED");
    const status = describeFinalStatus({
      verdict: "NO-GO",
      progressPct: 90,
      failed: [{ system: "Library", detail: "library unavailable", result: "FAIL" }],
      allRequiredOnline: false,
    });
    expect(status.headline).toBe("ADEPT UI SETUP REQUIRED");
    expect(status.items).toContain("Library: library unavailable");
  });

  it("optional unavailable does not block GO or say essentials are missing", () => {
    const status = describeFinalStatus({
      verdict: "GO",
      progressPct: 100,
      failed: [],
      setupOptional: [],
      allRequiredOnline: true,
    });
    expect(status.headline).toBe("ADEPT UI READY — GO");
    expect(status.itemKind).toBe("none");
    expect(status.items).toEqual([]);
    expect(JSON.stringify(status)).not.toMatch(/essential/i);
  });

  it("an idle on-demand system stays ON DEMAND and does not look failed", () => {
    const board = buildStartupBoard(SNAPSHOT, [check("studio_api_health", "Studio API", "PASS")]);
    const video = board.flatMap((section) => section.rows).find((item) => item.label === "Video Runtime");
    const remote = board.flatMap((section) => section.rows).find((item) => item.label === "Remote Access");
    expect(video?.badge).toBe("ON DEMAND");
    expect(remote?.badge).toBe("ON DEMAND");
    expect(video?.badge).not.toBe("FAILED");
    const status = describeFinalStatus({
      verdict: "GO",
      progressPct: 100,
      failed: [],
      allRequiredOnline: true,
    });
    expect(status.headline).toBe("ADEPT UI READY — GO");
  });

  it("withholds GO when a payload claims GO and a required failure together", () => {
    const status = describeFinalStatus({
      verdict: "GO",
      progressPct: 100,
      failed: [{ system: "Voice", detail: "router unavailable", result: "FAIL" }],
      allRequiredOnline: true,
    });
    expect(status.contradiction).toBe(true);
    expect(status.headline).toBe("ADEPT UI SETUP REQUIRED");
    expect(status.headline).not.toMatch(/READY — GO/);
    expect(status.items).toEqual(["Voice: router unavailable"]);
  });

  it("drops Cloud 1.2 from optional setup names so it cannot become a warning", () => {
    const status = describeFinalStatus({
      verdict: "GO",
      progressPct: 100,
      failed: [],
      setupOptional: [{ name: "Cloud 1.2" }, { name: "Video Runtime" }],
      allRequiredOnline: true,
    });
    expect(status.items).toEqual(["Video Runtime"]);
    expect(JSON.stringify(status)).not.toMatch(/Cloud 1\.2/);
  });

  it("does not say Bringing after startup is complete", () => {
    const done = describeFinalStatus({
      verdict: "GO",
      progressPct: 100,
      failed: [],
      allRequiredOnline: true,
    });
    expect(done.progressLabel).toBe("Startup Complete");
    expect(done.phaseTitle).not.toMatch(/Bringing/);
    const pending = describeFinalStatus({
      verdict: undefined,
      progressPct: 40,
      allRequiredOnline: false,
    });
    expect(pending.progressLabel).toBe("Bringing Adept UI Online");
    expect(pending.message).not.toMatch(/ALL SYSTEMS ONLINE/);
  });
});
