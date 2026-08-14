import { describe, expect, it } from "vitest";
import { CHARACTER_STYLE_OPTIONS } from "../../character/types";
import { CONTENT_NAV } from "../navEntries";
import { candidateProgress } from "./types";
import type { PropCandidate } from "./types";

function cand(partial: Partial<PropCandidate>): PropCandidate {
  return {
    id: "c1",
    prop_id: "p1",
    index: 0,
    job_id: "j1",
    status: "queued",
    source: "local",
    family: "zimage",
    model: "zimage",
    provenance_label: "LOCAL — Z-Image Turbo — Description Guided",
    conditioning: "description_guided",
    take_label: "Look 1",
    ...partial,
  };
}

describe("Prop Creator Express contracts", () => {
  it("places Prop Creator beside Character Creator", () => {
    const tabs = CONTENT_NAV.filter((item) => item.kind === "tab").map((item) => item.id);
    expect(tabs.indexOf("prop_creator")).toBe(tabs.indexOf("characters") + 1);
    const entry = CONTENT_NAV.find((item) => item.kind === "tab" && item.id === "prop_creator");
    expect(entry && entry.kind === "tab" ? entry.label : "").toBe("Prop Creator");
  });

  it("reuses the Character style registry including Cartoon and Concept Art", () => {
    const values = CHARACTER_STYLE_OPTIONS.map((o) => o.value);
    expect(values).toContain("documentary_realism");
    expect(values).toContain("graphic_novel");
    expect(values).toContain("stylized_3d_animation");
    expect(values).toContain("cartoon");
    expect(values).toContain("concept_art");
  });

  it("counts four looks as one Prop progress, not four props", () => {
    const candidates = [0, 1, 2, 3].map((index) =>
      cand({ id: `c${index}`, index, status: index < 2 ? "complete" : "generating" }),
    );
    const progress = candidateProgress(candidates);
    expect(progress.total).toBe(4);
    expect(progress.done).toBe(2);
    expect(progress.percent).toBe(50);
  });

  it("treats drafts as unsaved production identity", () => {
    const draft = { id: "draft", approved_asset_id: null as string | null, library_asset_id: "" };
    const approved = { id: "live", approved_asset_id: "asset-1", library_asset_id: "asset-1" };
    const production = [draft, approved].filter((p) => Boolean(p.approved_asset_id));
    expect(production.map((p) => p.id)).toEqual(["live"]);
  });

  it("keeps Express on the shared core, not a Standard-only path", async () => {
    const src = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./PropCreatorPanel.tsx", import.meta.url), "utf8"),
    );
    expect(src).toContain('variant="express"');
    expect(src).toContain("PropCreatorCore");
  });
});
