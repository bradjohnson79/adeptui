// Definitive test: spawn manager via bootstrap, keep parent ALIVE 30s, poll :8759 every 3s.
// Reveals whether the Node-spawned manager exits at ~15s (watch_once) or only on parent exit.
import { startRuntimeBootstrap, controlPlaneReachable, getBootstrapSupervisorPid } from "../../studio-web/runtime/bootstrap.ts";

async function main(): Promise<number> {
  const reachedBefore = await controlPlaneReachable();
  console.log("reachable_before:", reachedBefore);
  if (reachedBefore) { console.log("manager already up — kill it first"); return 2; }

  const result = await startRuntimeBootstrap({ log: (m) => console.log("[alive-test]", m) });
  console.log("spawned pid=", result.supervisorPid);

  for (let i = 0; i < 10; i++) {
    await new Promise((r) => setTimeout(r, 3000));
    const up = await controlPlaneReachable();
    const elapsed = (i + 1) * 3;
    console.log(`t=${elapsed}s :8759_up=${up}`);
    if (!up) { console.log(`MANAGER EXITED at ~${elapsed}s (parent still alive)`); break; }
  }
  console.log("supervisorPid:", getBootstrapSupervisorPid());
  return 0;
}

main().then((code) => process.exit(code));
