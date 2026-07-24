/**
 * Run critical Playwright suite and ensure audit report artifacts exist.
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outDir = path.join(root, "artifacts", "functional-audit");
fs.mkdirSync(outDir, { recursive: true });

const npx = process.platform === "win32" ? "npx.cmd" : "npx";
const child = spawn(
  npx,
  ["playwright", "test", "--grep", "@critical"],
  { cwd: root, stdio: "inherit", shell: true, env: process.env },
);

child.on("exit", (code) => {
  const reportMd = path.join(outDir, "AUDIT_REPORT.md");
  if (!fs.existsSync(reportMd)) {
    fs.writeFileSync(
      reportMd,
      [
        "# Functional Audit Report",
        "",
        `Generated: ${new Date().toISOString()}`,
        "",
        `Playwright critical suite exit code: ${code ?? 1}`,
        "",
        "See audit-results.json and playwright-report/ for details.",
        "",
      ].join("\n"),
    );
  }
  process.exit(code ?? 1);
});
