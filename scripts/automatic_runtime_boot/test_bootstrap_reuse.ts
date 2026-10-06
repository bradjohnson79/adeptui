import { startRuntimeBootstrap, controlPlaneReachable, getBootstrapSupervisorPid } from "../../studio-web/runtime/bootstrap.ts";

async function main(): Promise<number> {
  const events: string[] = [];
  const result = await startRuntimeBootstrap({
    onEvent: (e) => events.push(e.type),
    log: (m) => console.log("[boot-test]", m),
  });

  console.log("reachable_before:", await controlPlaneReachable());
  console.log("events:", JSON.stringify(events));
  console.log("result:", JSON.stringify(result));
  console.log("supervisorPid:", getBootstrapSupervisorPid());

  // Warm/reuse contract: manager already up -> reused=true, no spawn (supervisorPid null), no Comfy restart.
  const ok =
    result.reused === true &&
    result.supervisorPid === null &&
    events.includes("checking") &&
    events.includes("reused");
  console.log("REUSE_CERT_OK=", ok);
  return ok ? 0 : 1;
}

main().then((code) => process.exit(code));
