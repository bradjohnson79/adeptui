/**
 * Shared hooks for the live-Beta certification subset (M5.0 Addendum 9).
 * Ensures each test starts from a deterministic surface and tears down install jobs / browser storage.
 */
import { test as base } from "@playwright/test";
import { resetLiveBetaTestSurface, waitForAppReady } from "../helpers/app";

export const test = base.extend({
  // eslint-disable-next-line no-empty-pattern
  page: async ({ page, request }, use) => {
    await waitForAppReady(request);
    await resetLiveBetaTestSurface(request, page);
    await use(page);
    await resetLiveBetaTestSurface(request, page);
  },
});

export { expect } from "@playwright/test";
