import { describe, expect, it } from "vitest";
import { buildSemanticPackage, buildSemanticSceneSummary } from "./semanticLabels";
import {
  createDefaultDocument,
  createFigure,
  createFurniture,
  renameFigure,
  setFigureRole,
} from "./state";

describe("PoseCraft Co-Director scene labels", () => {
  it("keeps permanent ids when renaming labels", () => {
    let scene = createDefaultDocument().currentScene;
    const female = scene.figures.find((f) => f.archetypeId === "adult-female")!;
    const idBefore = female.id;
    scene = renameFigure(scene, female.id, "Maya");
    scene = setFigureRole(scene, female.id, "lead");
    const after = scene.figures.find((f) => f.id === idBefore)!;
    expect(after.id).toBe(idBefore);
    expect(after.name).toBe("Maya");
    expect(after.role).toBe("lead");
  });

  it("builds semantic package with labels and roles for Image Gen / Storyboard", () => {
    let doc = createDefaultDocument();
    let scene = doc.currentScene;
    const female = scene.figures.find((f) => f.archetypeId === "adult-female")!;
    const male = scene.figures.find((f) => f.archetypeId === "adult-male")!;
    scene = renameFigure(scene, female.id, "Maya");
    scene = setFigureRole(scene, female.id, "lead");
    scene = renameFigure(scene, male.id, "Daniel");
    scene = setFigureRole(scene, male.id, "supporting");
    const table = createFurniture("table-medium", 1);
    table.name = "Coffee Table";
    scene = { ...scene, primitives: [...scene.primitives, table], revision: scene.revision + 1 };
    doc = { ...doc, currentScene: scene };

    const pack = buildSemanticPackage(doc);
    expect(pack.figures.some((f) => f.label === "Maya" && f.role === "lead" && f.id === female.id)).toBe(true);
    expect(pack.figures.some((f) => f.label === "Daniel" && f.role === "supporting")).toBe(true);
    expect(pack.objects.some((o) => o.label === "Coffee Table" && o.furnitureKind === "table-medium")).toBe(true);

    const summary = buildSemanticSceneSummary(scene);
    expect(summary).toContain("Maya");
    expect(summary).toContain("Daniel");
    expect(summary).toContain("Coffee Table");
    expect(summary).not.toMatch(/Green figure|blue figure/i);
  });

  it("defaults figure role to unspecified", () => {
    const figure = createFigure("adult-female");
    expect(figure.role).toBe("unspecified");
  });
});
