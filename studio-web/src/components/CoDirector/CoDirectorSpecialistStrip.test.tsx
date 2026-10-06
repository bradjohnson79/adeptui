import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { CoDirectorSpecialistStrip } from "./CoDirectorSpecialistStrip";

vi.mock("./CoDirectorSession", () => ({
  useCoDirectorSession: () => ({ uiContext: { projectId: "", selectedCharacterIds: [] } }),
}));

vi.mock("../../api", () => ({
  api: {
    m211Specialists: () => Promise.resolve({ specialists: [] }),
    getCharacterCoverage: () => Promise.resolve({}),
  },
}));

describe("specialist dropdown", () => {
  it("uses the shared dark select", () => {
    const html = renderToStaticMarkup(createElement(CoDirectorSpecialistStrip));
    expect(html).toContain("adept-select");
    expect(html).toContain('data-testid="codirector-specialist-select"');
  });
});
