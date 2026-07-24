/** Kill listeners on E2E ports (Windows-friendly). */
import { execSync } from "node:child_process";

const ports = [5173, 8742, 8765];

function pidsOnPort(port) {
  try {
    const out = execSync(
      `powershell -NoProfile -Command "(Get-NetTCPConnection -LocalPort ${port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique) -join ','"`,
      { encoding: "utf8" },
    ).trim();
    if (!out) return [];
    return out.split(",").map((s) => Number(s.trim())).filter((n) => n > 0);
  } catch {
    return [];
  }
}

const killed = new Set();
for (const port of ports) {
  for (const pid of pidsOnPort(port)) {
    if (killed.has(pid)) continue;
    try {
      execSync(`taskkill /PID ${pid} /T /F`, { stdio: "ignore" });
      killed.add(pid);
      console.log(`[e2e-stop] killed pid=${pid} (port ${port})`);
    } catch {
      console.log(`[e2e-stop] could not kill pid=${pid}`);
    }
  }
}
console.log(`[e2e-stop] done (killed ${killed.size})`);
