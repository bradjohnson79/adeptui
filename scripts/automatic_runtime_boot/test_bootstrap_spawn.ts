// Certifies the bootstrap SPAWN path: control plane down -> spawn canonical supervisor
// (detached, stdio->log file) -> manager binds :8759 -> reuses surviving Studio API + Comfy.
// Run after killing ONLY the manager (:8759); Studio API + Comfy must survive (detached).
import { startRuntimeBootstrap, controlPlaneReachable, getBootstrapSupervisorPid } from "../../studio-web/runtime/bootstrap.ts";

async function main(): Promise<number> {
  const events: string[] = [];
  const reachedBefore = await controlPlaneReachable();
  console.log("reachable_before_spawn:", reachedBefore);

  const result = await startRuntimeBootstrap({
    onEvent: (e) => events.push(e.type + (e.type === "failed" ? ":" + (e as { reason?: string }).reason : "")),
    log: (m) => console.log("[spawn-test]", m),
  });

  console.log("events:", JSON.stringify(events));
  console.log("result:", JSON.stringify(result));
  console.log("supervisorPid:", getBootstrapSupervisorPid());

  // Wait a bit and re-probe — manager must STAY up (not exit like the earlier 31728).
  await new Promise((r) => setTimeout(r, 6000));
  const reachedAfter = await controlPlaneReachable();
  console.log("reachable_after_6s:", reachedAfter);

  const ok =
    result.reused === false &&
    typeof result.supervisorPid === "number" &&
    events.includes("starting") &&
    events.includes("online") &&
    reachedAfter === true;
  console.log("SPAWN_CERT_OK=", ok);
  return ok ? 0 : 1;
}

main().then((code) => process.exit(code));
