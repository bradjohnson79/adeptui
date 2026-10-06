import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const python = path.join(root, "studio-api", ".venv", "Scripts", "python.exe");

const probe = `
import hashlib, json, sqlite3, sys
path = sys.argv[1]
con = sqlite3.connect("file:" + path.replace("\\\\", "/") + "?mode=ro", uri=True)
digest = hashlib.sha256()
tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
counts = {}
for name in tables:
    rows = con.execute(f'SELECT * FROM "{name}"').fetchall()
    counts[name] = len(rows)
    for row in rows:
        digest.update(repr(row).encode("utf-8", "replace"))
header = open(path, "rb").read(100)
con.close()
print(json.dumps({
    "projects": counts.get("projects", 0),
    "scenes": counts.get("scenes", 0),
    "tables": len(tables),
    "digest": digest.hexdigest(),
    "changeCounter": int.from_bytes(header[24:28], "big"),
}))
`;

export function logicalSnapshot(dbPath) {
  if (!fs.existsSync(dbPath) || !fs.existsSync(python)) return null;
  const result = spawnSync(python, ["-c", probe, dbPath], { encoding: "utf8", windowsHide: true });
  if (result.status !== 0) return { error: (result.stderr || "").slice(-500) };
  return JSON.parse(result.stdout.trim().split(/\r?\n/).pop());
}

export function preservationVerdict(before, after) {
  if (!before || !after || before.error || after.error) {
    return { pass: false, semanticMutations: null, reason: "snapshot unavailable" };
  }
  const same = before.digest === after.digest && before.projects === after.projects;
  return {
    pass: same,
    semanticMutations: same ? 0 : 1,
    projectCountPreserved: before.projects === after.projects,
    physicalHeaderChanged: before.changeCounter !== after.changeCounter,
  };
}
