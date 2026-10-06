import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

/**
 * Guards the smallest workspace-open path for ?workspace=codirector. Co-Director
 * is an overlay, not a routed workspace tab, so a /project/:id?workspace=codirector
 * deep-link must open the Co-Director popup over the project (keeping sceneId
 * context via the existing binding) instead of falling through to project home.
 * The fix must not redesign chrome — it only opens the existing overlay once.
 */
describe("ProjectEditor ?workspace=codirector deep-link", () => {
  const src = readFileSync(new URL("./ProjectEditor.tsx", import.meta.url), "utf8");

  it("recognizes codirector / co-director as a Co-Director deep-link", () => {
    expect(src).toContain('"codirector"');
    expect(src).toContain('"co-director"');
    expect(src).toContain("isCoDirectorDeepLink");
  });

  it("opens the Co-Director overlay instead of landing on project home", () => {
    expect(src).toContain("openCoDirector()");
    // The underlying tab stays on the project landing so a workspace remains
    // mounted under the overlay (matches the c5 popup-over-workspace model).
    expect(src).toContain('setTab("home")');
  });

  it("opens the overlay once per deep-link arrival, not on every effect re-run", () => {
    expect(src).toContain("codirectorDeepLinkOpenedRef");
    expect(src).toContain("codirectorDeepLinkOpenedRef.current = true");
  });

  it("does not redirect away from the project URL or drop sceneId context", () => {
    // The deep-link must NOT navigate to /co-director (that would drop the
    // /project/:id route and require a separate binding cycle). It opens the
    // overlay in place.
    const deepLinkBlock = src.slice(
      src.indexOf("isCoDirectorDeepLink"),
      src.indexOf("ROUTING CONTRACT"),
    );
    expect(deepLinkBlock).not.toContain("navigate(coDirectorProjectPath");
    expect(deepLinkBlock).not.toContain("navigate({ pathname: `/project/${id}`");
  });
});
