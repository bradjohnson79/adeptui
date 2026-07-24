import fs from "node:fs";
import path from "node:path";
import type { Page, TestInfo } from "@playwright/test";
import { redact, redactDeep } from "./redact";

export type AuditDefect = {
  testName: string;
  severity: "Blocker" | "Critical" | "High" | "Medium" | "Low";
  uiRoute?: string;
  userAction?: string;
  expected?: string;
  actual?: string;
  consoleError?: string;
  failedEndpoint?: string;
  responseStatus?: number | string;
  backendException?: string;
  screenshotPath?: string;
  tracePath?: string;
  suspectedRootCause?: string;
  confirmedRootCause?: string;
  filesChanged?: string[];
  verificationResult?: string;
};

export type AuditEvent = {
  at: string;
  kind: string;
  detail: Record<string, unknown>;
};

const RENDER_PHASE_WARNING =
  /Cannot update a component (`?\w+`?) while rendering a different component/i;

export class AuditObserver {
  events: AuditEvent[] = [];
  defects: AuditDefect[] = [];
  consoleErrors: string[] = [];
  pageErrors: string[] = [];
  failedRequests: Array<{ url: string; error: string }> = [];
  apiFailures: Array<{ url: string; status: number; durationMs: number }> = [];
  slowApis: Array<{ url: string; status: number; durationMs: number }> = [];
  renderPhaseWarnings: string[] = [];
  allowlistedUrlPatterns: RegExp[] = [];

  constructor(
    private readonly page: Page,
    private readonly testInfo: TestInfo,
  ) {}

  attach() {
    this.page.on("console", (msg) => {
      const text = redact(msg.text());
      this.events.push({
        at: new Date().toISOString(),
        kind: `console.${msg.type()}`,
        detail: { text },
      });
      if (msg.type() === "error") this.consoleErrors.push(text);
      if (RENDER_PHASE_WARNING.test(text)) this.renderPhaseWarnings.push(text);
      if (msg.type() === "warning" && RENDER_PHASE_WARNING.test(text)) {
        this.renderPhaseWarnings.push(text);
      }
    });
    this.page.on("pageerror", (err) => {
      const text = redact(err.message);
      this.pageErrors.push(text);
      this.events.push({
        at: new Date().toISOString(),
        kind: "pageerror",
        detail: { text, stack: redact(err.stack || "") },
      });
    });
    this.page.on("requestfailed", (req) => {
      const url = redact(req.url());
      if (this.isAllowlisted(url)) return;
      const failure = req.failure()?.errorText || "requestfailed";
      this.failedRequests.push({ url, error: failure });
      this.events.push({
        at: new Date().toISOString(),
        kind: "requestfailed",
        detail: { url, error: failure },
      });
    });
    this.page.on("response", async (res) => {
      const url = redact(res.url());
      if (!url.includes("/api/")) return;
      const status = res.status();
      const timing = res.request().timing();
      const durationMs = Math.max(0, (timing?.responseEnd || 0) - (timing?.requestStart || 0));
      if (durationMs > 5000) {
        this.slowApis.push({ url, status, durationMs });
      }
      if (status >= 400 && !this.isAllowlisted(url)) {
        this.apiFailures.push({ url, status, durationMs });
        this.events.push({
          at: new Date().toISOString(),
          kind: "api.failure",
          detail: { url, status, durationMs },
        });
      }
    });
  }

  allow(pattern: RegExp) {
    this.allowlistedUrlPatterns.push(pattern);
  }

  private isAllowlisted(url: string) {
    return this.allowlistedUrlPatterns.some((re) => re.test(url));
  }

  assertHealthyBrowser() {
    if (this.renderPhaseWarnings.length) {
      throw new Error(
        `React render-phase update warning(s):\n${this.renderPhaseWarnings.join("\n")}`,
      );
    }
    if (this.pageErrors.length) {
      throw new Error(`Unhandled pageerror(s):\n${this.pageErrors.join("\n")}`);
    }
  }

  recordDefect(defect: AuditDefect) {
    this.defects.push(redactDeep(defect));
  }

  async snapshot(label: string) {
    const dir = path.join("artifacts", "functional-audit", "screenshots");
    fs.mkdirSync(dir, { recursive: true });
    const file = path.join(
      dir,
      `${this.testInfo.title.replace(/[^\w.-]+/g, "_")}_${label}.png`,
    );
    await this.page.screenshot({ path: file, fullPage: true });
    return file;
  }

  flush() {
    const outDir = path.join("artifacts", "functional-audit");
    fs.mkdirSync(outDir, { recursive: true });
    const resultsPath = path.join(outDir, "audit-results.json");
    let existing: { runs?: unknown[]; defects?: AuditDefect[] } = {};
    if (fs.existsSync(resultsPath)) {
      try {
        existing = JSON.parse(fs.readFileSync(resultsPath, "utf8"));
      } catch {
        existing = {};
      }
    }
    const run = redactDeep({
      test: this.testInfo.title,
      file: this.testInfo.file,
      status: this.testInfo.status,
      errors: this.testInfo.errors?.map((e) => e.message),
      consoleErrors: this.consoleErrors,
      pageErrors: this.pageErrors,
      failedRequests: this.failedRequests,
      apiFailures: this.apiFailures,
      slowApis: this.slowApis,
      renderPhaseWarnings: this.renderPhaseWarnings,
      events: this.events.slice(-200),
      defects: this.defects,
      at: new Date().toISOString(),
    });
    const runs = [...(existing.runs || []), run];
    const defects = [...(existing.defects || []), ...this.defects];
    fs.writeFileSync(resultsPath, JSON.stringify({ runs, defects }, null, 2));
  }
}
