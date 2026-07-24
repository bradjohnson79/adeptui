import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "@playwright/test";
import { createTempProject, deleteProject, openSetup, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

test.describe("@critical @isolated a11y", () => {
  test("setup page has no critical axe violations", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `A11y ${Date.now()}`);
    try {
      await openSetup(page, project.id);
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa"])
        .analyze();
      const critical = results.violations.filter((v) =>
        ["critical", "serious"].includes(v.impact || ""),
      );
      if (critical.length) {
        observer.recordDefect({
          testName: test.info().title,
          severity: "High",
          uiRoute: `/project/${project.id}?workspace=setup`,
          expected: "No critical/serious axe violations",
          actual: critical.map((v) => v.id).join(", "),
          suspectedRootCause: "Accessibility markup gaps on Setup Wizard",
        });
      }
      // Soft gate: document but only fail on critical impact
      const blockers = critical.filter((v) => v.impact === "critical");
      expect(blockers, JSON.stringify(blockers, null, 2)).toEqual([]);
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
