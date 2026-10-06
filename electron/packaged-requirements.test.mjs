import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { auditPackagedTree, pywin32InstallPlan, renderSelectedRequirements, selectRequirements } from "./packaged-requirements-contract.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const pins = fs.readFileSync(path.join(root, "electron", "packaged-requirements.txt"), "utf8");

test("pywin32 stays on Windows and is not selected for macOS or Linux", () => {
  const plan = pywin32InstallPlan(pins);
  assert.equal(plan.windowsPresent, true);
  assert.equal(plan.macosInstallAttempts, 0);
  assert.equal(plan.linuxInstallAttempts, 0);
});

test("the macOS install file is generated from the same pin list", () => {
  const rendered = renderSelectedRequirements(pins, "darwin");
  assert.equal(selectRequirements(rendered, "darwin").selected.some((row) => row.name === "pywin32"), false);
  assert.match(rendered, /pywin32-ctypes==0\.2\.3/);
  assert.equal(selectRequirements(rendered, "darwin").selected.some((row) => row.name === "uvicorn"), true);
  assert.equal(fs.existsSync(path.join(root, "electron", "packaged-requirements-darwin.txt")), false);
  assert.equal(fs.existsSync(path.join(root, "electron", "packaged-requirements-macos.txt")), false);
});

test("the Mac package audit rejects Windows binaries and keeps pywin32-ctypes", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "adept-mac-audit-"));
  fs.mkdirSync(path.join(dir, "pywin32_ctypes"), { recursive: true });
  fs.writeFileSync(path.join(dir, "pywin32_ctypes", "library.py"), "ok\n");
  assert.deepEqual(auditPackagedTree(dir), []);
  fs.mkdirSync(path.join(dir, "pywin32"), { recursive: true });
  fs.writeFileSync(path.join(dir, "helper.dll"), "");
  const problems = auditPackagedTree(dir);
  assert.equal(problems.length, 2);
  fs.writeFileSync(path.join(dir, "libfoo.dylib"), "");
  assert.equal(auditPackagedTree(dir).some((item) => item.endsWith(".dylib")), false);
  assert.equal(auditPackagedTree(dir, { rejectMac: true }).some((item) => item.endsWith(".dylib")), true);
  fs.rmSync(dir, { recursive: true, force: true });
});

test("Windows staging still copies the Windows runtime and does not pip-filter pywin32", () => {
  const source = fs.readFileSync(path.join(root, "electron", "scripts", "stage-packaged-runtime.mjs"), "utf8");
  assert.match(source, /python-3\.11\.9-embed-amd64\.zip/);
  assert.match(source, /robocopy/);
  assert.doesNotMatch(source, /packaged-requirements-contract/);
  assert.doesNotMatch(source, /sys_platform/);
});
