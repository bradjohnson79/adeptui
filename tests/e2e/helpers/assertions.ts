import { expect, type Page } from "@playwright/test";
import type { AuditObserver } from "./observer";

export async function expectNoStuckConfiguring(page: Page, componentId: string) {
  const card = page.getByTestId(`setup-card-${componentId}`);
  await expect(card).toBeVisible();
  const text = await card.innerText();
  expect(text).not.toMatch(/Configuring…\s*$/m);
  // Estimating without progress is OK briefly; stuck Estimating for long is bad — caller waits first.
  expect(await card.getAttribute("data-status")).not.toBe("installing");
}

export function expectObserverClean(observer: AuditObserver) {
  observer.assertHealthyBrowser();
  const unexpected5xx = observer.apiFailures.filter((f) => f.status >= 500);
  expect(unexpected5xx, JSON.stringify(unexpected5xx)).toEqual([]);
}
