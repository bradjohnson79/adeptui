import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  openCharacterSheetInImageGenerator,
  openCharacterSheetInLibrary,
  seedImageGeneratorFromSheet,
} from "./characterSheetDestinations";

const here = dirname(fileURLToPath(import.meta.url));

describe("characterSheetDestinations", () => {
  const store = new Map<string, string>();

  beforeEach(() => {
    store.clear();
    vi.stubGlobal("sessionStorage", {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        store.set(key, value);
      },
      removeItem: (key: string) => {
        store.delete(key);
      },
      clear: () => store.clear(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("seeds Image Generator then navigates with character + asset", () => {
    const onGoTab = vi.fn();
    openCharacterSheetInImageGenerator(onGoTab, {
      characterId: "char-1",
      assetId: "asset-9",
    });
    expect(sessionStorage.getItem("adept_cis_seed")).toBe(JSON.stringify({ assetId: "asset-9" }));
    expect(onGoTab).toHaveBeenCalledWith("imagegen", { characterId: "char-1", assetId: "asset-9" });
  });

  it("opens Library with the sheet asset", () => {
    const onGoTab = vi.fn();
    openCharacterSheetInLibrary(onGoTab, "asset-9");
    expect(onGoTab).toHaveBeenCalledWith("library", { assetId: "asset-9" });
  });

  it("does not navigate without an asset", () => {
    const onGoTab = vi.fn();
    seedImageGeneratorFromSheet("");
    openCharacterSheetInLibrary(onGoTab, " ");
    openCharacterSheetInImageGenerator(onGoTab, { characterId: "char-1", assetId: "" });
    expect(onGoTab).not.toHaveBeenCalled();
  });
});

describe("character sheet destination wiring (source)", () => {
  it("threads onGoTab from Express, Standard, and shared core", () => {
    const core = readFileSync(resolve(here, "CharacterCore.tsx"), "utf8");
    const compact = readFileSync(resolve(here, "../CoDirector/characters/CharacterCompactView.tsx"), "utf8");
    const workspace = readFileSync(resolve(here, "../CharacterProfileWorkspace.tsx"), "utf8");
    const editor = readFileSync(resolve(here, "../../pages/ProjectEditor.tsx"), "utf8");
    const content = readFileSync(resolve(here, "../CoDirector/CoDirectorProjectContent.tsx"), "utf8");
    expect(core).toContain("onGoTab={onGoTab}");
    expect(compact).toContain("onGoTab={onGoTab}");
    expect(workspace).toContain("onGoTab={onGo}");
    expect(editor).toContain("onGo={go}");
    expect(content).toContain("<CharacterCompactView");
    expect(content).toContain("onGoTab={onGoTab}");
  });

  it("Create Character 409 does not unmount the compact form", () => {
    const compact = readFileSync(resolve(here, "../CoDirector/characters/CharacterCompactView.tsx"), "utf8");
    const createFn = compact.slice(
      compact.indexOf("const handleCreate"),
      compact.indexOf("character-compact-create"),
    );
    expect(createFn).toContain("PROFILE_NAME_ALREADY_EXISTS");
    expect(createFn).toContain("setActionNotice");
    expect(createFn).toContain("existingId");
    expect(createFn).not.toContain("setError(e.message)");
  });
});
