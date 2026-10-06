import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { ActionWithHelp, HelpTip } from "./HelpTip";

const here = dirname(fileURLToPath(import.meta.url));

function src(rel: string) {
  return readFileSync(join(here, rel), "utf8");
}

function buttonNestCount(html: string) {
  return (html.match(/<button\b/g) || []).length;
}

describe("HelpTip", () => {
  it("renders a real button with an accessible label and no nested button", () => {
    const html = renderToStaticMarkup(
      createElement(HelpTip, { label: "What is Preflight?", content: "Checks the scene before generate." }),
    );
    expect(html).toContain("<button");
    expect(html).toContain('aria-label="What is Preflight?"');
    expect(html).toContain("?");
    expect(buttonNestCount(html)).toBe(1);
    expect(html).not.toMatch(/<button[^>]*>[\s\S]*<button/);
  });
});

describe("ActionWithHelp", () => {
  it("keeps the primary button and HelpTip as siblings", () => {
    const html = renderToStaticMarkup(
      createElement(
        ActionWithHelp,
        { help: { label: "Co-Director Preflight", content: "Inspects the scene.", text: "Co-Director Preflight" } },
        createElement("button", { type: "button", "data-testid": "timeline-toolbar-preflight" }, "Preflight"),
      ),
    );
    expect(html).toContain('class="action-with-help"');
    expect(html).toContain('role="group"');
    expect(html).toContain("Preflight");
    expect(html).toContain('data-testid="timeline-toolbar-preflight"');
    expect(buttonNestCount(html)).toBe(2);
    expect(html).toContain(
      'data-testid="timeline-toolbar-preflight">Preflight</button><button type="button" class="help-tip"',
    );
    expect(html.indexOf("timeline-toolbar-preflight")).toBeLessThan(html.indexOf("help-tip"));
  });
});

describe("invalid HelpTip nesting removed", () => {
  it("TimelineToolbar Preflight is a sibling of Help, not a parent", () => {
    const file = src("timeline-master/TimelineToolbar.tsx");
    expect(file).toContain("ActionWithHelp");
    expect(file).not.toMatch(/data-testid="timeline-toolbar-preflight"[\s\S]{0,400}<Help /);
  });

  it("Production menu items do not wrap HelpTip", () => {
    const file = src("dashboard/ProductionMenu.tsx");
    expect(file).toContain("production-menu__item-row");
    expect(file).not.toMatch(/role="menuitem"[\s\S]{0,500}<HelpTip /);
  });

  it("DirectorTracks action buttons do not wrap HelpBtn", () => {
    const file = src("DirectorTracks.tsx");
    expect(file).toContain("ActionWithHelp");
    expect(file).not.toMatch(/<(button)[^>]*>[\s\S]{0,200}<(HelpBtn|HelpTip) /);
  });

  it("TimelineMasterPanel action buttons do not wrap HelpBtn", () => {
    const file = src("timeline-master/TimelineMasterPanel.tsx");
    expect(file).toContain("ActionWithHelp");
    expect(file).not.toContain("HelpBtn");
    expect(file).not.toMatch(/<(button)[^>]*>[\s\S]{0,200}<HelpTip /);
  });
});
