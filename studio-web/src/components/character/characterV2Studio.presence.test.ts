import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("Character Creator V2 studio wiring", () => {
  const studio = readFileSync(new URL("./CharacterV2Studio.tsx", import.meta.url), "utf8");
  const progress = readFileSync(new URL("./CharacterGenerationProgress.tsx", import.meta.url), "utf8");

  it("uses the canonical media resolver and one progress component", () => {
    expect(studio).toContain("characterMediaUrl");
    expect(studio).not.toContain("/api/projects/${");
    expect(studio).not.toContain("/assets/${encodeURIComponent(assetId)}/file");
    expect(studio).toContain("CharacterGenerationProgress");
    expect(studio).toContain("cc-v2-generator-select");
    expect(studio).toContain("cc-v2-img-${view}");
    expect(progress).toContain("cc-v2-progress-${view}");
    expect(studio).toContain('view="sheet"');
  });

  it("shows optional Close-up for Standard and Express", () => {
    expect(studio).toContain("Close-up — Optional");
    expect(studio).toContain('mode === "express"');
    expect(studio).toContain("Create Close-up");
    expect(studio).toContain("Generate Character Angles");
    expect(studio).toContain("Upload Angles");
    expect(studio).toContain("cc-v2-upload-${angle}");
    expect(studio).toContain("Replace Upload");
    expect(studio).not.toContain("They cannot be uploaded.");
    expect(studio).toContain("Waiting its turn…");
    expect(studio).toContain("cc-v2-multiview-live");
    expect(studio).toContain('{approved ? "Approved" : "Approve"}');
    expect(studio).toContain("disabled={!!busy || !img || approved}");
    expect(studio).toContain("sheetGate");
    expect(studio).toContain("frontApproved");
    expect(studio).toContain("approvedFrontAssetId");
    expect(studio).toContain("Rebuild Character Sheet");
    expect(studio).toContain("cc-v2-sheet-hint");
    expect(studio).toContain("Character Sheet ready to create.");
    expect(studio).not.toContain("enrichOk &&");
    expect(studio).toContain("cc-v2-regen-${angle}");
    expect(studio).toContain("cc-v2-regen-sheet");
    expect(studio).toContain("Creating Character Sheet…");
    expect(studio).toContain("anglesRuntimeHint");
    expect(studio).toContain("disabled={!!busy || jobActive || !frontOk || !state?.engine?.available}");
    expect(studio).toContain("key={row.name}");
    expect(studio).toContain("cc-v2-angles-stage");
    expect(studio).not.toContain("Wait for Co-Director to finish studying Front");
    expect(studio).toContain("Remove this ${label} picture?");
    expect(studio).not.toContain("Wonder3D creates Side");
    expect(studio).not.toContain("cc-v2-generate-back");
    expect(studio).not.toContain("Create Back View");
    expect(studio).toContain("cc-v2-vision-error");
    expect(studio).toContain("cc-v2-vision-failed");
    expect(studio).toContain("cc-v2-open-library");
    expect(studio).toContain("cc-v2-use-imagegen");
    expect(studio).toContain("Open in Library");
    expect(studio).toContain("Use in Image Generator");
    expect(studio).toContain("openCharacterSheetInLibrary");
    expect(studio).toContain("openCharacterSheetInImageGenerator");
  });

  it("allows Front from the profile when there is no reference", () => {
    expect(studio).toContain("hasReference");
    expect(studio).toContain("Front will be created from the Character Profile description");
    expect(studio).toContain("Front will be created from the reference picture");
    expect(studio).not.toContain("Add a character reference first");
    expect(studio).not.toContain("disabled={!!busy || jobActive || (view === \"front\" && !hasReference)");
    expect(studio).toContain("referenceSignature");
    expect(studio).toContain("viewOpAvailable");
    expect(studio).toContain("cc-v2-unavailable-${view}");
  });
});
