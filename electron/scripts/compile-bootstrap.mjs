import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ts = require("typescript");
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const source = fs.readFileSync(path.join(root, "studio-web", "runtime", "bootstrap.ts"), "utf8");
const transpiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    esModuleInterop: true,
  },
  fileName: "bootstrap.ts",
});
const outDir = path.join(root, "electron", "build", "compiled");
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, "bootstrap.cjs"), transpiled.outputText);
console.log("compiled bootstrap");
