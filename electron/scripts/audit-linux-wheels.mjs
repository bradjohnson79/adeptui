import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { selectRequirements } from "../packaged-requirements-contract.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const pins = fs.readFileSync(path.join(root, "electron", "packaged-requirements.txt"), "utf8");
const selected = selectRequirements(pins, "linux").selected;

function compatible(filename) {
  const name = filename.toLowerCase();
  if (!name.endsWith(".whl")) return false;
  const platform = name.slice(0, -4).split("-").pop() || "";
  if (platform.includes("win") || platform.includes("macosx")) return false;
  if (platform === "any") return true;
  return (platform.includes("manylinux") && platform.includes("x86_64")) || platform.includes("linux_x86_64");
}

async function lookup(row) {
  const version = (row.requirement.match(/==\s*([^\s;]+)/) || [])[1];
  if (!version) return { name: row.name, version: "", blocker: "unpinned" };
  const url = `https://pypi.org/pypi/${encodeURIComponent(row.name)}/${encodeURIComponent(version)}/json`;
  const response = await fetch(url);
  if (!response.ok) return { name: row.name, version, blocker: `pypi ${response.status}` };
  const body = await response.json();
  const files = (body.urls || []).map((item) => item.filename);
  const wheels = files.filter(compatible);
  return { name: row.name, version, blocker: wheels.length ? "" : "no linux x64 wheel", files: files.slice(0, 8) };
}

const blockers = [];
const queue = [...selected];
const workers = Array.from({ length: 8 }, async () => {
  while (queue.length) {
    const row = queue.shift();
    try {
      const result = await lookup(row);
      if (result.blocker) blockers.push(result);
    } catch (err) {
      blockers.push({ name: row.name, blocker: String(err.message || err) });
    }
  }
});
await Promise.all(workers);
blockers.sort((a, b) => a.name.localeCompare(b.name));
const pywin32 = selectRequirements(pins, "linux").selected.filter((row) => row.name === "pywin32").length;
console.log(`PYWIN32 INSTALL ATTEMPT ON LINUX = ${pywin32}`);
console.log(`LINUX REQUIREMENTS = ${selected.length}`);
if (blockers.length) {
  console.error("LINUX BACKEND DEPENDENCY BLOCKER");
  for (const row of blockers) {
    console.error(`${row.name}==${row.version || "?"} ${row.blocker}`);
    if (row.files) console.error(`  files: ${row.files.join(", ")}`);
  }
  process.exit(1);
}
console.log("LINUX WHEEL AUDIT = PASS");
