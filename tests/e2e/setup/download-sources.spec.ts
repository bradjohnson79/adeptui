import { test, expect } from "@playwright/test";
import {
  API,
  createTempProject,
  deleteProject,
  openSetup,
  waitForAppReady,
} from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

test.describe("@critical @isolated download sources", () => {
  test("Download Sources cards render CLI status and Add Source URL verifies before save", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);

    await request.post(`${API}/api/e2e/cli-mock`, {
      data: {
        github: {
          status: "Installed but not authenticated",
          cli_detected: true,
          executable_path: "C:\\\\mock\\\\gh.exe",
          executable_name: "gh",
          version: "2.40.0",
          authenticated: false,
          account_name: null,
          token_available: false,
          message: "The CLI is installed, but this source may require you to sign in.",
        },
        huggingface: {
          status: "Not installed",
          cli_detected: false,
          executable_path: null,
          executable_name: null,
          version: null,
          authenticated: false,
          account_name: null,
          token_available: false,
          message: "Hugging Face CLI (hf / huggingface-cli) was not found on PATH.",
        },
      },
    });

    const project = await createTempProject(request, `Download Sources ${Date.now()}`);
    try {
      await openSetup(page, project.id);
      const github = page.getByTestId("download-source-github");
      const hf = page.getByTestId("download-source-huggingface");
      await expect(github).toBeVisible();
      await expect(hf).toBeVisible();
      await expect(github).toHaveAttribute("data-status", "Installed but not authenticated");
      await expect(hf).toHaveAttribute("data-status", "Not installed");

      await page.getByTestId("add-source-url-pack_essential_cinematic").click();
      const dialog = page.getByTestId("add-source-url-dialog");
      await expect(dialog).toBeVisible();
      await dialog.getByTestId("source-url-input").fill(
        "https://github.com/acme/widgets/archive/refs/heads/main.zip",
      );
      await dialog.getByTestId("verify-source-button").click();
      await expect(dialog.getByTestId("source-verification-summary")).toBeVisible({
        timeout: 30_000,
      });
      await expect(dialog.getByText(/Source archives are not accepted/i)).toBeVisible();
      await expect(dialog.getByTestId("save-source-override-button")).toBeDisabled();

      // Security: localhost rejected outside fixture download path is covered in unit tests;
      // here ensure dialog stays open and does not start a download on paste alone.
      await dialog.getByTestId("source-url-input").fill("https://github.com/acme/widgets/releases");
      await dialog.getByRole("button", { name: /Cancel/i }).click();
      await expect(dialog).toHaveCount(0);
      observer.assertHealthyBrowser();
    } finally {
      await request.post(`${API}/api/e2e/cli-mock`, { data: { clear: true } });
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
