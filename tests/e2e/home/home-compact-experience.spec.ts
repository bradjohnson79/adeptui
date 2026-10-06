import { test, expect, type Page } from "@playwright/test";
import { waitForAppReady } from "../helpers/app";

async function gotoHome(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("generation-studio-home")).toBeVisible({ timeout: 30_000 });
}

test.describe("Home compact experience", () => {
  test("feature card, three-row library, search, and fullscreen Co-Director", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await page.setViewportSize({ width: 1920, height: 1080 });
    await gotoHome(page);

    await expect(page.getByTestId("codirector-launch-composer")).toHaveCount(0);
    await expect(page.getByTestId("codirector-launch-card")).toBeVisible();
    await expect(page.getByTestId("codirector-launch-image")).toBeVisible();
    await expect(page.getByTestId("enter-codirector")).toBeVisible();
    await expect(page.getByTestId("timeline-launch-card")).toBeVisible();
    await expect(page.getByTestId("magi-launch-card")).toBeVisible();

    const results = page.getByTestId("home-library-results");
    await expect(results).toBeVisible({ timeout: 20_000 });
    const cards = results.locator(".project-cover-card");
    await expect(cards.first()).toBeVisible();

    const metrics = await results.evaluate((el) => {
      const grid = el.querySelector(".project-library-grid") as HTMLElement | null;
      const cards = [...el.querySelectorAll(".project-cover-card")] as HTMLElement[];
      if (!grid || !cards.length) return null;
      const styles = getComputedStyle(grid);
      const gap = parseFloat(styles.rowGap || styles.gap || "16") || 16;
      const rowHeight = cards[0].getBoundingClientRect().height;
      const columns = (styles.gridTemplateColumns || "").split(" ").filter(Boolean).length;
      const box = el.getBoundingClientRect();
      const fourth = cards[columns * 3];
      const fourthBox = fourth?.getBoundingClientRect();
      return {
        height: parseFloat(getComputedStyle(el).height) || 0,
        clientHeight: el.clientHeight,
        scrollHeight: el.scrollHeight,
        rowHeight,
        gap,
        columns,
        cardCount: cards.length,
        fourthHidden: !fourthBox || fourthBox.top >= box.bottom - 1,
      };
    });
    expect(metrics).toBeTruthy();
    expect(Math.abs(metrics!.height - (metrics!.rowHeight * 3 + metrics!.gap * 2))).toBeLessThan(1);
    expect(metrics!.fourthHidden).toBe(true);
    if (metrics!.cardCount > metrics!.columns * 3) {
      expect(metrics!.scrollHeight).toBeGreaterThan(metrics!.clientHeight + 4);
    }

    const search = page.getByLabel("Search projects");
    await results.evaluate((el) => {
      el.scrollTop = el.scrollHeight;
    });
    await search.fill("zzzz-no-such-home-project");
    await expect(page.getByText("No matching projects")).toBeVisible();
    await search.fill("");
    await expect(results).toBeVisible();
    const scrolledAfterReset = await results.evaluate((el) => el.scrollTop);
    expect(scrolledAfterReset).toBe(0);

    await page.getByRole("button", { name: "List", exact: true }).click();
    await expect(results.locator(".project-library-grid.list")).toBeVisible();
    await page.getByRole("button", { name: "Grid", exact: true }).click();

    const context = (await page.getByTestId("codirector-project-context").textContent()) || "";
    await page.getByTestId("enter-codirector").click();
    await expect(page).toHaveURL(/\/co-director/, { timeout: 15_000 });
    await expect(page.getByTestId("codirector-fullscreen-shell")).toHaveAttribute("data-mode", "fullscreen");
    expect(await page.getByTestId("codirector-fullscreen-shell").count()).toBe(1);
    if (/Active project:/.test(context)) {
      await expect(page).toHaveURL(/projectId=/);
    }
  });
});
