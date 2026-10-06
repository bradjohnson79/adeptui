import { describe, expect, it } from "vitest";
import { CONTENT_NAV } from "../navEntries";
import { PRODUCTION_MENU_CATALOG } from "../../../core/productionMenu";
import { WORKSPACES, resolveWorkspace } from "../../../core/workspaces";
import {
  ENV_CREATOR_ASPECT_DEFAULT,
  ENV_CREATOR_ASPECTS,
  ENV_CREATOR_GENERATORS,
  buildEnvironmentPlanSummary,
  emptyEnvironmentCreatorPlanning,
  environmentCreatorGenerateBlockReason,
  serializeEnvironmentCreatorPlan,
} from "./environmentCreatorPlanning";

describe("Environment Creator contracts", () => {
  it("Express CONTENT_NAV labels scene_creator as Environment Creator", () => {
    const entry = CONTENT_NAV.find((item) => item.kind === "tab" && item.id === "scene_creator");
    expect(entry).toMatchObject({ kind: "tab", id: "scene_creator", label: "Environment Creator" });
  });

  it("Express Environment Creator mounts real ERS surface (not coming-next shell)", async () => {
    const launcher = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("../SceneCreator/SceneCreatorExpressLauncher.tsx", import.meta.url), "utf8"),
    );
    const surface = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./EnvironmentCreatorSurface.tsx", import.meta.url), "utf8"),
    );
    expect(launcher).toContain("EnvironmentCreatorSurface");
    expect(launcher).not.toContain("environment-creator-ers-next");
    expect(launcher).not.toContain("coming next");
    expect(surface).toContain("environment-creator-empty");
    expect(surface).toContain("hydrateExistingSheets: true");
    expect(surface).not.toContain("EnvironmentReferenceSheetPanel");
    expect(surface).toContain("ERSGenerationMonitor");
    expect(surface).toContain("useErsGeneration");
    expect(surface).toContain('spatialMapId: null');
    expect(surface).toContain("EntityPicker");
    expect(surface).toContain("environment-creator-choose-source");
    expect(surface).toContain("uploadAsset");
    expect(surface).toContain("persistThenOpenSceneCreator");
    expect(surface).not.toContain("onSaveSpatialMap");
    expect(surface).not.toContain("restitchCompositeAssetId");
    // Planning surface sections
    expect(surface).toContain("environment-creator-prompt");
    expect(surface).toContain("environment-creator-characters");
    expect(surface).toContain("environment-creator-props");
    expect(surface).toContain("environment-creator-story-theme");
    expect(surface).toContain("environment-creator-aspect");
    expect(surface).toContain("environment-creator-generator");
    expect(surface).toContain("environment-creator-plan-summary");
    expect(surface).toContain("Reference Image (optional)");
    expect(surface).not.toContain("Choose a source environment image first.");
  });

  it("Standard has Environment Creator entry; Scene Creator is retired to Image Generator", () => {
    expect(WORKSPACES.environmentcreator.label).toBe("Environment Creator");
    expect(resolveWorkspace("environmentcreator")).toBe("environmentcreator");
    expect(resolveWorkspace("environment-creator")).toBe("environmentcreator");
    // Scene Creator Standard retired (Image Generator v1.1 triad): stale
    // links land on the Image Generator, never a removed workspace.
    expect(resolveWorkspace("scenecreator")).toBe("imagegen");
    expect(resolveWorkspace("scene_creator")).toBe("imagegen");
    expect(resolveWorkspace("mastersheet")).toBe("imagegen");
    expect(resolveWorkspace("scene-creator")).toBe("imagegen");

    const pre = PRODUCTION_MENU_CATALOG.find((c) => c.id === "pre-production");
    const ids = (pre?.entries || []).map((e) => e.id);
    expect(ids).toContain("environmentcreator");
    expect(ids).not.toContain("scenecreator");
    expect(pre?.entries.find((e) => e.id === "environmentcreator")?.label).toBe("Environment Creator");
  });

  it("does not resurrect Spatial Map as Environment Creator", async () => {
    const surface = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./EnvironmentCreatorSurface.tsx", import.meta.url), "utf8"),
    );
    const workspace = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("../../environment-creator/EnvironmentCreatorWorkspace.tsx", import.meta.url), "utf8"),
    );
    expect(surface).not.toContain("SpatialMapPanel");
    expect(workspace).not.toContain("SpatialMapPanel");
    expect(WORKSPACES.spatial.label).toBe("Spatial Map");
    expect(WORKSPACES.environmentcreator.label).not.toBe("Spatial Map");
  });

  it("exposes Name and Global on the Environment Creator surface", async () => {
    const surface = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./EnvironmentCreatorSurface.tsx", import.meta.url), "utf8"),
    );
    expect(surface).toContain("environment-creator-name");
    expect(surface).toContain("environment-creator-global");
    expect(surface).toContain("GlobalScopeField");
  });

  it("uses one saveEnvironment handler for top and bottom Save Environment", async () => {
    const surface = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./EnvironmentCreatorSurface.tsx", import.meta.url), "utf8"),
    );
    const planning = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./environmentCreatorPlanning.ts", import.meta.url), "utf8"),
    );
    const api = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("../../../api.ts", import.meta.url), "utf8"),
    );
    expect(surface).toContain("const saveEnvironment = useCallback");
    expect(surface).not.toContain("saveEnvironmentTop");
    expect(surface).not.toContain("saveEnvironmentBottom");
    expect(surface).toContain('placement="top"');
    expect(surface).toContain('placement="bottom"');
    expect(surface).toContain('onSave={() => void saveEnvironment()}');
    expect(surface.match(/onSave=\{\(\) => void saveEnvironment\(\)\}/g)?.length).toBe(2);
    expect(surface).toContain("environment-creator-save-${placement}");
    expect(surface).toContain('data-save-command="saveEnvironment"');
    expect(surface).toContain("disabled={busy}");
    expect(surface).toContain("api.environmentReferenceSheet.upsert");
    const saveFn = surface.slice(
      surface.indexOf("const saveEnvironment = useCallback"),
      surface.indexOf("const selectHydratedSheet"),
    );
    expect(saveFn).toContain("api.environmentReferenceSheet.upsert");
    expect(saveFn).not.toContain("ers.start");
    expect(saveFn).not.toContain("onGoTab");
    expect(saveFn).not.toContain("scrollIntoView");
    expect(saveFn).not.toContain("scrollTo");
    expect(planning).toContain("buildEnvironmentCreatorSaveBody");
    expect(planning).toContain("validateEnvironmentCreatorSave");
    expect(planning).toContain("isGlobal: Boolean(state.isGlobal)");
    expect(planning).toContain("is_global: Boolean(state.isGlobal)");
    expect(api).toContain("/save");
  });

  it("Character and Prop Express keep a single Save — Environment only adds dual entry points", async () => {
    const character = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("../../character/CharacterActions.tsx", import.meta.url), "utf8"),
    );
    const prop = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("../PropCreator/PropCreatorCore.tsx", import.meta.url), "utf8"),
    );
    expect(character).toContain("Save Character");
    expect(character).not.toContain("character-save-top");
    expect(prop).toContain("pc.save");
    expect(prop).not.toContain("prop-creator-save-top");
  });

  it("planning gating: optional ref, prompt-required-if-no-ref, chars/props not required", () => {
    const empty = emptyEnvironmentCreatorPlanning();
    expect(environmentCreatorGenerateBlockReason({
      planning: empty,
      providerReady: true,
      providerI2IReady: true,
      generatorCatalogAvailable: true,
    })).toMatch(/description|reference/i);

    const promptOnly = { ...empty, environmentPrompt: "Foggy pier at dusk" };
    expect(environmentCreatorGenerateBlockReason({
      planning: promptOnly,
      providerReady: true,
      providerI2IReady: false,
      generatorCatalogAvailable: true,
    })).toBeNull();

    const refOnly = { ...empty, referenceImageAssetId: "asset-1" };
    expect(environmentCreatorGenerateBlockReason({
      planning: refOnly,
      providerReady: true,
      providerI2IReady: true,
      generatorCatalogAvailable: true,
    })).toBeNull();

    const refNeedsI2I = { ...empty, referenceImageAssetId: "asset-1" };
    expect(environmentCreatorGenerateBlockReason({
      planning: refNeedsI2I,
      providerReady: true,
      providerI2IReady: false,
      generatorCatalogAvailable: true,
    })).toMatch(/Requires Setup|image-to-image/i);

    expect(ENV_CREATOR_ASPECT_DEFAULT).toBe("16:9");
    expect([...ENV_CREATOR_ASPECTS]).toEqual(["1:1", "4:3", "3:4", "16:9", "9:16", "21:9"]);
    expect(ENV_CREATOR_GENERATORS.map((g) => g.id)).toEqual(["gpt-image-2"]);
    expect(ENV_CREATOR_GENERATORS.map((g) => g.label).join(" ")).not.toMatch(/2\.5/);
  });

  it("serializes planning for ERS start context", () => {
    const state = {
      ...emptyEnvironmentCreatorPlanning(),
      environmentPrompt: "Rainy alley",
      referenceImageAssetId: "ref-9",
      storyTheme: { label: "Noir", source: "story" as const, override: "" },
      aspectRatio: "21:9" as const,
      generator: "gpt-image-2" as const,
      characters: [
        {
          characterId: "c1",
          name: "Korri",
          thumbAssetId: "t1",
          crsAssetId: "crs1",
          crsApproved: true,
        },
      ],
      props: [
        {
          propId: "p1",
          name: "Lantern",
          prsAssetId: "prs1",
          thumbAssetId: "pt1",
          assignment: { kind: "used_by" as const, characterId: "c1" },
        },
      ],
    };
    const snap = serializeEnvironmentCreatorPlan(state);
    expect(snap).toMatchObject({
      environmentPrompt: "Rainy alley",
      referenceImageAssetId: "ref-9",
      storyTheme: "Noir",
      aspectRatio: "21:9",
      generator: "gpt-image-2",
      characters: [{ characterId: "c1", crsAssetId: "crs1" }],
      props: [{ propId: "p1", prsAssetId: "prs1", assignment: "used_by", characterId: "c1" }],
    });
    const summary = buildEnvironmentPlanSummary(state);
    expect(summary.some((line) => line.includes("ENVIRONMENT") || line.includes("Description") || line.includes("Rainy"))).toBe(true);
    expect(summary.some((line) => line.includes("Korri"))).toBe(true);
    expect(summary.some((line) => line.includes("Lantern"))).toBe(true);
  });

  it("validates name and snapshots dirty persist fields including Global", async () => {
    const {
      emptyEnvironmentCreatorPlanning,
      validateEnvironmentCreatorSave,
      environmentCreatorPersistSnapshot,
      buildEnvironmentCreatorSaveBody,
      planningFromSavedSheet,
    } = await import("./environmentCreatorPlanning");
    const empty = emptyEnvironmentCreatorPlanning();
    expect(validateEnvironmentCreatorSave(empty)).toMatchObject({ ok: false, field: "name" });
    const named = { ...empty, name: "Anadriya's Quarters", isGlobal: true, environmentPrompt: "cabin" };
    expect(validateEnvironmentCreatorSave(named)).toEqual({ ok: true });
    expect(environmentCreatorPersistSnapshot(named)).not.toEqual(environmentCreatorPersistSnapshot(empty));
    const body = buildEnvironmentCreatorSaveBody(named, "sheet-1");
    expect(body).toMatchObject({
      sheetId: "sheet-1",
      name: "Anadriya's Quarters",
      isGlobal: true,
      is_global: true,
      environmentPrompt: "cabin",
    });
    const hydrated = planningFromSavedSheet(
      {
        name: "Anadriya's Quarters",
        description: "persisted cabin",
        isGlobal: true,
        provenance: {
          details: {
            environmentCreatorPlan: {
              name: "Anadriya's Quarters",
              isGlobal: true,
              environmentPrompt: "persisted cabin",
              aspectRatio: "16:9",
              generator: "gpt-image-2",
              characters: [],
              props: [],
            },
          },
        },
      },
      empty,
    );
    expect(hydrated.environmentPrompt).toBe("persisted cabin");
    expect(hydrated.isGlobal).toBe(true);
  });

  it("exposes Co-Director planning access paths", async () => {
    const planning = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./environmentCreatorPlanning.ts", import.meta.url), "utf8"),
    );
    const surface = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./EnvironmentCreatorSurface.tsx", import.meta.url), "utf8"),
    );
    expect(planning).toContain("getEnvironmentCreatorPlanningSnapshot");
    expect(planning).toContain("publishEnvironmentCreatorPlanning");
    expect(planning).toContain("subscribeEnvironmentCreatorPlanning");
    expect(surface).toContain("publishEnvironmentCreatorPlanning");
    expect(surface).toContain("getBible");
  });

  it("wires Create New plus red Delete Environment through one modal contract", async () => {
    const surface = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./EnvironmentCreatorSurface.tsx", import.meta.url), "utf8"),
    );
    expect(surface).toContain("environment-creator-new");
    expect(surface).toContain("environment-creator-delete-top");
    expect(surface).toContain("environment-creator-delete-bottom");
    expect(surface).toContain('data-delete-command={label === "Delete Snapshot" ? "deleteSnapshot" : "deleteEnvironment"}');
    expect(surface).toContain('data-save-command="saveEnvironment"');
    expect(surface).toContain("CreatorProfileDeleteModal");
    expect(surface).toContain('entityType="environment"');
    expect(surface).toContain("handleCreateNew");
    expect(surface).toContain("handleDeleteClick");
    expect(surface).toContain("handleConfirmDelete");
    expect(surface).toContain('className="danger"');
    expect(surface).toContain("selectedSheetOwned");
    expect(surface).toContain("if (boundSheetId && boundSheetId !== ers.sheetId) return");
  });

  it("exposes Approve as Environment direct-approval chrome on one identity contract", async () => {
    const surface = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("./EnvironmentCreatorSurface.tsx", import.meta.url), "utf8"),
    );
    const api = await import("node:fs").then((fs) =>
      fs.readFileSync(new URL("../../../api.ts", import.meta.url), "utf8"),
    );
    // Button next to Change from Library / Upload Image / Remove, both branches.
    expect(surface).toContain("environment-creator-approve-source");
    expect(surface.match(/environment-creator-approve-source/g)?.length).toBe(2);
    expect(surface).toContain("Approve as Environment");
    expect(surface).toContain("Approved Environment ✓");
    expect(surface).toContain("handleApproveAsEnvironment");
    // Approval is a committed action: persists identity first when dirty, then
    // approves through the ERS contract and refreshes the lower sheets panel.
    const approveFn = surface.slice(
      surface.indexOf("const handleApproveAsEnvironment = useCallback"),
      surface.indexOf("const handleRemoveReference = useCallback"),
    );
    expect(approveFn).toContain("api.environmentReferenceSheet.upsert");
    expect(approveFn).toContain("api.environmentReferenceSheet.approveReference");
    expect(approveFn).toContain("refreshProjectSheets");
    expect(approveFn).not.toContain("ers.start");
    // Remove on an approved image confirms + clears approval (no dangling approval).
    const removeFn = surface.slice(
      surface.indexOf("const handleRemoveReference = useCallback"),
      surface.indexOf("const handleCreateNew = useCallback"),
    );
    expect(removeFn).toContain("window.confirm");
    expect(removeFn).toContain("approved Environment Reference");
    expect(removeFn).toContain("api.environmentReferenceSheet.clearApproval");
    // API client converges on the same sheet identity routes.
    expect(api).toContain("approve-reference");
    expect(api).toContain("clear-approval");
  });

  it("Co-Director ers.delete_sheet imports stay inside the app package", async () => {
    const handler = await import("node:fs").then((fs) =>
      fs.readFileSync(
        new URL(
          "../../../../../studio-api/app/codirector/tools/handlers/environment_reference_sheet.py",
          import.meta.url,
        ),
        "utf8",
      ),
    );
    expect(handler).toContain("def preview_delete_sheet");
    expect(handler).toContain("from ....creator_scope.service import delete_preview_payload");
    expect(handler).toContain("from ....environment_reference_sheet.store import delete_environment_sheet");
    expect(handler).not.toContain("from .....creator_scope");
    expect(handler).not.toContain("from .....environment_reference_sheet");
  });
});
