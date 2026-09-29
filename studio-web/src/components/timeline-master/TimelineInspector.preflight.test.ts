import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = dirname(fileURLToPath(import.meta.url));
const inspector = readFileSync(join(here, "TimelineInspector.tsx"), "utf8");
const panel = readFileSync(join(here, "SceneProductionReadinessPanel.tsx"), "utf8");

describe("Timeline Inspector Preflight is always mounted", () => {
  it("renders Production Readiness before selection branches", () => {
    const panelIdx = inspector.indexOf("<SceneProductionReadinessPanel");
    const sceneBranch = inspector.indexOf("{(selection.kind === null || selection.kind === \"scene\") && (");
    const batchBranch = inspector.indexOf("{selection.kind === \"batch\" && selectedBatch");
    expect(panelIdx).toBeGreaterThan(-1);
    expect(panelIdx).toBeLessThan(sceneBranch);
    expect(panelIdx).toBeLessThan(batchBranch);
    expect(inspector).toContain("onRunPreflight={onPreflightRecheck}");
  });

  it("keeps generator quality out of Advanced and under Generation", () => {
    const generation = inspector.indexOf('testId="timeline-batch-generation"');
    const advanced = inspector.indexOf('testId="timeline-batch-advanced"');
    const batchSlice = inspector.slice(generation, advanced);
    expect(generation).toBeGreaterThan(-1);
    expect(advanced).toBeGreaterThan(generation);
    expect(batchSlice).toContain('megapixelsTestId="timeline-batch-resolution"');
    expect(batchSlice).toContain('qualityTestId="timeline-batch-quality"');
    expect(batchSlice).toContain("<NativeAudioCapability");
    expect(inspector).not.toContain("None (generator has no native audio)");
    expect(inspector).not.toContain("isMiniMaxH3Generator");
    expect(inspector).not.toContain("isLtx25Generator");
    const afterAdvanced = inspector.slice(advanced, advanced + 500);
    expect(afterAdvanced).toContain("<LoRASelector");
    expect(afterAdvanced).not.toContain("timeline-batch-resolution");
    expect(afterAdvanced).not.toContain("timeline-batch-quality");
  });

  it("exposes scene Spoken Language that stays empty until the creator chooses", () => {
    const generation = inspector.indexOf('testId="timeline-inspector-generation"');
    const nextAccordion = inspector.indexOf("<InspectorAccordion", generation + 1);
    const generationSlice = inspector.slice(generation, nextAccordion > generation ? nextAccordion : generation + 2500);
    const apiSrc = readFileSync(join(here, "../../api.ts"), "utf8");
    expect(generationSlice).toContain('data-testid="timeline-spoken-language"');
    expect(generationSlice).toContain("Spoken Language");
    expect(generationSlice).toContain("Choose language…");
    expect(generationSlice).toContain("directorTimelinePutSceneSpokenLanguage");
    expect(generationSlice).toContain("The language characters speak in this scene. Needed when someone has a line.");
    expect(inspector).toContain("sceneSpokenLanguageFromMaster");
    expect(inspector).toContain('master?.sceneLanguage || master?.spokenLanguage?.sceneLanguage || ""');
    expect(inspector).not.toContain('|| "en"');
    expect(generationSlice).not.toContain("Cade");
    expect(apiSrc).toContain("directorTimelineGetSpokenLanguage:");
    expect(apiSrc).toContain("directorTimelinePutSpokenLanguage:");
    expect(apiSrc).toContain("directorTimelinePutSceneSpokenLanguage:");
    expect(apiSrc).toContain("/spoken-language");
  });

  it("does not hide Production Readiness inside Advanced-only Scene accordion", () => {
    const advanced = inspector.indexOf('testId="timeline-inspector-advanced"');
    const afterAdvanced = inspector.slice(advanced, advanced + 800);
    expect(afterAdvanced).not.toContain("<SceneProductionReadinessPanel");
  });

  it("Production Readiness always offers a visible Preflight action", () => {
    expect(panel).toContain('data-testid="timeline-inspector-preflight"');
    expect(panel).toContain('{checking ? "Checking…" : "Preflight"}');
    expect(panel).toContain("onRunPreflight");
    expect(panel).toContain('prev === "checking"');
    expect(panel).toContain("refresh()");
    expect(panel).toContain('testId="scene-readiness-location"');
    expect(panel).toContain('testId="scene-readiness-references"');
    expect(panel).toContain('testId="scene-readiness-cast"');
    expect(panel).toContain('testId="scene-readiness-voice"');
    expect(panel).toContain('if (status === "advisory") return "ADVISORY"');
    expect(panel).toContain("Ready with ${advisoryCount} advisories");
    expect(panel).toContain('data-testid="timeline-preflight-advisory"');
    expect(panel).toContain("timeline-preflight-advisory-list");
    expect(panel).toContain('["warning", "advisory", "info"]');
    expect(panel).toContain('const gateLabel = technicalLock ? "Locked"');
    expect(panel).not.toContain("window.alert");
  });
});
