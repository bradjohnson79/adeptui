import { describe, expect, it } from "vitest";
import { interpretAtlasLookUtterance, normalizeAtlasLook } from "./atlasLook";

describe("atlas look contract", () => {
  it("maps Co-Director language onto the same object the UI uses", () => {
    const look = interpretAtlasLookUtterance("Make the Atlas look more architectural and brighten it.");
    expect(look.style).toBe("architectural");
    expect(look.lighting).toBe("bright_planning");
    const metal = interpretAtlasLookUtterance("Match the corridor's metallic appearance closely.");
    expect(metal.sourceAppearance).toBe("strong");
    expect(metal.style).toBe("auto_match_source");
  });

  it("keeps defaults when nothing is said", () => {
    const look = normalizeAtlasLook(null);
    expect(look.style).toBe("auto_match_source");
    expect(look.detail).toBe("balanced");
    expect(look.presentation).toBe("roofless");
    expect(look.showGrid).toBe(false);
  });
});
