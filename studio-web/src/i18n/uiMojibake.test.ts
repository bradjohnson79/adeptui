import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const ROOTS = ["components", "pages", "core", "i18n"].map((dir) =>
  join(__dirname, "..", dir),
);

const FORBIDDEN = [
  Buffer.from([0xc3, 0xa2, 0xe2, 0x82, 0xac]), // â€
  Buffer.from([0xc3, 0x82, 0xc2, 0xb7]), // Â·
  Buffer.from([0xc3, 0x82, 0x20]), // Â + space
  Buffer.from([0xc3, 0x83, 0xe2, 0x80, 0x94]), // Ã—  (UTF-8 × misread as Windows-1252)
];

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    const stat = statSync(full);
    if (stat.isDirectory()) {
      walk(full, out);
      continue;
    }
    if (name === "uiMojibake.test.ts") continue;
    if (!/\.(ts|tsx|js|jsx|json)$/.test(name)) continue;
    out.push(full);
  }
  return out;
}

describe("production UI source has no mojibake", () => {
  it("scans components, pages, core, and i18n for known UTF-8 misreads", () => {
    const hits: string[] = [];
    for (const root of ROOTS) {
      for (const file of walk(root)) {
        const data = readFileSync(file);
        for (const seq of FORBIDDEN) {
          if (data.includes(seq)) {
            hits.push(relative(join(__dirname, ".."), file).replace(/\\/g, "/"));
            break;
          }
        }
      }
    }
    expect(hits, `mojibake in:\n${hits.join("\n")}`).toEqual([]);
  });
});
