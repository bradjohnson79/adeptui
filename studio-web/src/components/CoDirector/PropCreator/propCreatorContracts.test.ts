import { describe, expect, it } from "vitest";
import { CHARACTER_STYLE_OPTIONS } from "../../character/types";
import { CONTENT_NAV } from "../navEntries";
import { PRODUCTION_MENU_CATALOG } from "../../../core/productionMenu";
import { resolveWorkspace } from "../../../core/workspaces";
import { candidateProgress } from "./types";
import type { PropCandidate } from "./types";
import { countSceneShotsForProp, countSpatialPlacementsForProp } from "./propUsage";

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
    provenance_label: "LOCAL - Z-Image Turbo - Description Guided",
    conditioning: "description_guided",
    take_label: "Look 1",
    ...partial,
  };
}

describe("Prop Creator Express contracts", () => {
  it("places Prop Creator immediately after Voice Creator", () => {
    const tabs = CONTENT_NAV.filter((item) => item.kind === "tab").map((item) => item.id);
    expect(tabs.indexOf("prop_creator")).toBe(tabs.indexOf("voice_creator") + 1);
    expect(tabs.indexOf("voice_creator")).toBe(tabs.indexOf("characters") + 1);
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

  it("keeps Co-Director Express on the shared core", async () => {
    const src = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./PropCreatorPanel.tsx", import.meta.url), "utf8"),
    );
    expect(src).toContain('variant="express"');
    expect(src).toContain("PropCreatorCore");
  });

  it("hosts Standard Prop | Advanced Prop tabs inside Express only", async () => {
    const fs = await import("node:fs");
    const core = fs.readFileSync(new URL("./PropCreatorCore.tsx", import.meta.url), "utf8");
    const advanced = fs.readFileSync(new URL("./PropAdvancedPanel.tsx", import.meta.url), "utf8");
    const express = core.slice(core.indexOf("function ExpressLayout"), core.indexOf("function StandardLayout"));
    expect(express).toContain('data-testid="prop-creator-tab-standard"');
    expect(express).toContain('data-testid="prop-creator-tab-advanced"');
    expect(express).toContain("<PropAdvancedPanel");
    expect(express).toContain("<GeneratorBlock");
    expect(express).toContain("<SavedPropBlock");
    expect(advanced).toContain('data-testid="prop-advanced-primary-prompt"');
    expect(advanced).toContain('data-testid="prop-advanced-type"');
    expect(advanced).toContain('data-testid="prop-advanced-reference"');
    expect(advanced).toContain('data-testid="prop-advanced-ref-upload"');
    expect(advanced).toContain('data-testid="prop-advanced-ref-library"');
    expect(advanced).toContain('data-testid="prop-advanced-ref-cd"');
    expect(advanced).toContain('data-testid="prop-advanced-ref-status"');
    expect(advanced).toContain('data-testid="prop-advanced-ref-thumb"');
    expect(advanced).toContain('data-testid="prop-advanced-ref-remove"');
    expect(advanced).toContain("Reference: Primary Design Look locked");
    expect(advanced).toContain("CharacterReferenceAssetPicker");
    expect(advanced).toContain("useOpenCoDirector");
    expect(advanced).toContain("prop_reference");
    expect(advanced).toContain('data-testid="prop-advanced-angles"');
    expect(advanced).toContain("ADDITIONAL_VIEWS_TITLE");
    expect(advanced).toContain("ADDITIONAL_VIEWS_HINT");
    expect(advanced).toContain("SHEET_COMPOSE_HINT_READY");
    expect(advanced).toContain("SHEET_COMPOSE_HINT_BLOCKED");
    expect(advanced).toContain("visiblePrimaryPreviewAssetId");
    expect(advanced).toContain("PropAssetPreview");
    expect(advanced).toContain('testId="prop-advanced-primary-image"');
    expect(advanced).toContain("canApprovePrimary");
    expect(advanced).toContain("canApproveView");
    expect(advanced).toContain("canComposeAdvancedSheet");
    const approval = fs.readFileSync(new URL("./propApproval.ts", import.meta.url), "utf8");
    expect(approval).toContain('ADDITIONAL_VIEWS_TITLE = "Additional Views (optional)"');
    expect(approval).toContain("Optional — add for stronger multi-angle consistency.");
    expect(approval).toContain("REQUIRED_PROP_VIEWS");
    expect(approval).toContain("approvedComposeViews");
    expect(approval).not.toContain('ADDITIONAL_VIEWS_TITLE = "Required Views"');
    expect(approval).not.toContain("Hero is optional");
    expect(approval).not.toContain("Approve Front, Back, Left, Right, Top, and Bottom");
    expect(advanced).toContain("prop-advanced-angle-${angle}");
    expect(advanced).toContain("prop-advanced-angle-${angle}-upload");
    expect(advanced).toContain('data-testid="prop-advanced-primary-upload"');
    expect(express).toContain('data-testid="prop-creator-section-saved-advanced"');
    expect(core).toContain('data-testid="prop-creator-upload-look"');
    expect(advanced).toContain("PROP_ADVANCED_ANGLE_KEYS");
    const typesSrc = fs.readFileSync(new URL("./types.ts", import.meta.url), "utf8");
    expect(typesSrc).toContain('"front"');
    expect(typesSrc).toContain('"hero"');
    expect(advanced).not.toContain("design-prompt");
    expect(advanced).not.toContain("angle-strip");
    expect(advanced).not.toContain("hero-optional");
  });
});


  it("glues Express Standard sections to character-core rhythm (no CharacterGeneratorPanel)", async () => {
    const fs = await import("node:fs");
    const core = fs.readFileSync(new URL("./PropCreatorCore.tsx", import.meta.url), "utf8");
    const express = core.slice(core.indexOf("function ExpressLayout"), core.indexOf("function StandardLayout"));
    expect(express).toContain('className="character-core__section"');
    expect(express).toContain('className="character-core__section-title"');
    expect(express).toContain(">Saved Prop<");
    expect(express).toContain(">Name / Style<");
    expect(express).toContain(">Description<");
    expect(express).toContain(">Reference<");
    expect(express).toContain(">Generator<");
    expect(express).toContain(">Actions<");
    expect(express).toContain(">Results<");
    // Order: Saved → Name/Style → Description → Reference → Generator → Actions → Results
    const order = [
      express.indexOf(">Saved Prop<"),
      express.indexOf(">Name / Style<"),
      express.indexOf(">Description<"),
      express.indexOf(">Reference<"),
      express.indexOf(">Generator<"),
      express.indexOf(">Actions<"),
      express.indexOf(">Results<"),
    ];
    expect(order.every((i) => i >= 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
    expect(core).toContain('characterCore.css');
    expect(core).not.toContain("CharacterGeneratorPanel");
    expect(core).toContain("character-core__reference-preview");
  });

describe("Prop Creator Production path (Express-only)", () => {
  it("uses the shared core with variant=express as the primary Production path", async () => {
    const workspace = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("../../prop-creator/PropCreatorWorkspace.tsx", import.meta.url), "utf8"),
    );
    expect(workspace).toContain('variant="express"');
    expect(workspace).not.toContain('variant="standard"');
    expect(workspace).toContain("PropCreatorCore");
    const core = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./PropCreatorCore.tsx", import.meta.url), "utf8"),
    );
    expect(core).toContain("function ExpressLayout");
    expect(core).toContain('data-testid="prop-creator-tab-advanced"');
    // StandardLayout may remain in-file for legacy reference but is not the Production primary mount.
    expect(core).toContain("function StandardLayout");
  });

  it("puts Prop Creator in Production Pre-Production near Environment Creator", () => {
    const pre = PRODUCTION_MENU_CATALOG.find((c) => c.id === "pre-production");
    const create = PRODUCTION_MENU_CATALOG.find((c) => c.id === "create");
    const ids = (pre?.entries || []).map((e) => e.id);
    expect(ids).toContain("propcreator");
    expect(ids).toContain("environmentcreator");
    expect((create?.entries || []).map((e) => e.id)).not.toContain("propcreator");
    expect(ids).not.toContain("timeline");
    expect(Math.abs(ids.indexOf("propcreator") - ids.indexOf("environmentcreator"))).toBe(1);
    expect(pre?.entries.find((e) => e.id === "propcreator")?.label).toBe("Prop Creator");
    expect(pre?.entries.find((e) => e.id === "propcreator")?.workspace).toBe("propcreator");
  });

  it("resolves Prop Creator workspace aliases", () => {
    expect(resolveWorkspace("propcreator")).toBe("propcreator");
    expect(resolveWorkspace("prop-creator")).toBe("propcreator");
    expect(resolveWorkspace("propCreator")).toBe("propcreator");
  });

  it("counts Spatial placements and Scene shots the same way delete unlinks them", () => {
    const spatial = countSpatialPlacementsForProp(
      [
        { props: [{ propId: "p1" }, { propId: "p2" }, { propId: "p1" }] },
        { props: [{ propId: null }, { propId: "p1" }] },
      ],
      "p1",
    );
    expect(spatial).toBe(3);
    const shots = countSceneShotsForProp(
      [
        { prop_entity_ids: ["p1", "x"] },
        { prop_entity_ids: ["y"], take_memory: { blocking: { prop_entity_ids: ["p1"] } } },
        { prop_entity_ids: ["z"] },
      ],
      "p1",
    );
    expect(shots).toBe(2);
  });
});

describe("Prop Creator save confirmation", () => {
  it("surfaces Prop profile saved only after a successful persist", async () => {
    const { persistSaveFeedback, PROP_PROFILE_SAVED_NOTICE } = await import("./usePropCreator");
    const ok = persistSaveFeedback(true);
    expect(ok.notice).toBe("Prop profile saved");
    expect(ok.notice).toBe(PROP_PROFILE_SAVED_NOTICE);
    expect(ok.error).toBeNull();
  });

  it("does not claim saved when persist fails", async () => {
    const { persistSaveFeedback } = await import("./usePropCreator");
    const fail = persistSaveFeedback(false, new Error("API rejected the Prop profile"));
    expect(fail.notice).toBeNull();
    expect(fail.error).toBe("API rejected the Prop profile");
    expect(String(fail.notice || "")).not.toMatch(/saved/i);
    expect(fail.error || "").not.toBe("Prop profile saved");
  });

  it("wires Save through the shared Express Standard Prop tab so confirm fires after persist", async () => {
    const fs = await import("node:fs");
    const hook = fs.readFileSync(new URL("./usePropCreator.ts", import.meta.url), "utf8");
    const persistFn = hook.slice(hook.indexOf("const persist ="), hook.indexOf("const save ="));
    const saveFn = hook.slice(hook.indexOf("const save ="), hook.indexOf("const newProp ="));
    expect(persistFn).toContain("propCreatorApi.upsert");
    expect(persistFn).not.toContain("PROP_PROFILE_SAVED_NOTICE");
    expect(persistFn).toContain("persistSaveFeedback(false");
    expect(saveFn.indexOf("await persist()")).toBeLessThan(saveFn.indexOf("persistSaveFeedback(true)"));
    expect(saveFn).toContain("flashNotice");

    const core = fs.readFileSync(new URL("./PropCreatorCore.tsx", import.meta.url), "utf8");
    expect(core).toContain("void pc.save()");
    const express = core.slice(core.indexOf("function ExpressLayout"), core.indexOf("function StandardLayout"));
    expect(express).toContain("<StatusBlock pc={pc} />");
    expect(express).toContain("<ActionsBlock pc={pc} />");
    expect(express).toContain('data-testid="prop-creator-tab-standard"');
  });
});