/**
 * Cross-platform launcher for Co-Director M2.4 developer scripts.
 */
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const apiDir = path.join(root, "studio-api");
const isWin = process.platform === "win32";
const venvPython = path.join(apiDir, ".venv", isWin ? "Scripts" : "bin", isWin ? "python.exe" : "python");
const python = fs.existsSync(venvPython) ? venvPython : "python";

const command = process.argv[2];
const scripts = {
  "validate-prompts": path.join(root, "scripts", "codirector_validate_prompts.py"),
  "list-specialists": path.join(root, "scripts", "codirector_list_specialists.py"),
  evaluate: path.join(root, "scripts", "codirector_eval.py"),
};

const script = scripts[command];
if (!script) {
  console.error(`Usage: node scripts/run-codirector-cli.mjs <${Object.keys(scripts).join("|")}>`);
  process.exit(1);
}

const result = spawnSync(python, [script], { stdio: "inherit", cwd: root, shell: isWin });
process.exit(result.status ?? 1);