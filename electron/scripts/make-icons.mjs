import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const emblem = path.join(root, "studio-web", "public", "brand", "adept-ui-emblem.webp");
const outDir = path.join(root, "electron", "icons");
const pngDir = path.join(outDir, "png");
fs.mkdirSync(pngDir, { recursive: true });

const python = path.join(root, "studio-api", ".venv", "Scripts", "python.exe");
const script = `
from PIL import Image
from pathlib import Path
src = Path(${JSON.stringify(emblem)})
out = Path(${JSON.stringify(outDir)})
png = Path(${JSON.stringify(pngDir)})
im = Image.open(src).convert("RGBA")
side = max(im.size)
canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
canvas.paste(im, ((side - im.size[0]) // 2, (side - im.size[1]) // 2), im)
master = canvas.resize((1024, 1024), Image.Resampling.LANCZOS)
master.save(out / "icon.png")
sizes = [16, 24, 32, 48, 64, 128, 256, 512]
icons = []
for size in sizes:
    frame = master.resize((size, size), Image.Resampling.LANCZOS)
    frame.save(png / f"{size}x{size}.png")
    icons.append(frame)
icons[-2].save(out / "icon.ico", sizes=[(s, s) for s in sizes if s <= 256])
print("icons-ok")
`;
const run = spawnSync(python, ["-c", script], { encoding: "utf8" });
if (run.status !== 0) {
  console.error(run.stderr || run.stdout);
  process.exit(run.status || 1);
}
console.log(run.stdout.trim());
