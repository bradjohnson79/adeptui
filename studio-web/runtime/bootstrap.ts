/**
 * Adept Runtime Bootstrap — canonical localhost lifecycle invocation.
 *
 * This is the ONE contract both the Vite dev server (localhost now) and the
 * future Electron main process call to bring the Adept background runtime
 * online automatically. It does NOT launch Comfy/Ollama/APIs one by one —
 * it invokes the canonical Runtime Supervisor (`run_runtime_supervisor.py serve`),
 * which owns those services as children.
 *
 * ComfyUI Protection Law: this never starts a second Comfy or adopts/kills an
 * external one. It only starts the Background Services manager when the
 * control plane (:8759) is down. An already-healthy owned Comfy is reused
 * by the supervisor itself.
 *
 * Environment-agnostic: Node built-ins only (net, child_process, path, fs).
 * No browser APIs. Safe to import from Vite config or Electron main.
 */
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, openSync } from "node:fs";
import { isAbsolute, resolve } from "node:path";
import { createConnection } from "node:net";

/** Loopback control plane port (canonical, see runtime_supervisor/constants.py). */
export const CONTROL_PORT = 8759;
export const CONTROL_HOST = "127.0.0.1";

export type BootstrapEvent =
  | { type: "checking" }
  | { type: "reused"; managerPid?: number }
  | { type: "starting"; supervisorPid: number }
  | { type: "online"; managerPid?: number }
  | { type: "failed"; reason: string };

export interface BootstrapOptions {
  /** Repo root (to locate the venv + supervisor launcher). Auto-detected if omitted. */
  repoRoot?: string;
  /**
   * Explicit interpreter. When set with launcherPath, the developer .venv walk is not used.
   * Packaged desktop passes the runtime shipped beside the app.
   */
  pythonPath?: string;
  /** Explicit supervisor launcher. Paired with pythonPath for a non-repo spawn. */
  launcherPath?: string;
  /** Working directory for the supervisor process. */
  cwd?: string;
  /** Log directory. Packaged desktop uses a folder under userData, not the repo. */
  logDir?: string;
  /** Extra environment for the supervisor. Does not replace ADEPT_RUNTIME_BOOTSTRAPPED. */
  extraEnv?: Record<string, string>;
  /**
   * Studio API port for a caller that spawns the supervisor. Omitted for the
   * browser/dev stack, which stays on 8758. Electron packaged mode does not
   * call serve; it starts uvicorn on the desktop port itself.
   */
  studioApiPort?: number;
  /**
   * When false, an open control plane is a collision: do not adopt it and do not spawn.
   * Default true keeps the dev/Vite behavior (reuse a healthy :8759).
   */
  reuseControlPlane?: boolean;
  /** Emit lifecycle events (Electron-ready contract). */
  onEvent?: (e: BootstrapEvent) => void;
  /** Probe timeout per attempt (ms). Default 800. */
  probeTimeoutMs?: number;
  /** Logger. Default console. */
  log?: (msg: string) => void;
}

let _supervisorPid: number | null = null;

/** True if the Background Services manager control plane is reachable (TCP accept on :8759). */
export function controlPlaneReachable(host = CONTROL_HOST, port = CONTROL_PORT, timeoutMs = 800): Promise<boolean> {
  return new Promise((resolve) => {
    let settled = false;
    const sock = createConnection({ host, port }, () => {
      settled = true;
      sock.destroy();
      resolve(true);
    });
    sock.setTimeout(timeoutMs);
    sock.on("timeout", () => {
      if (!settled) {
        settled = true;
        sock.destroy();
        resolve(false);
      }
    });
    sock.on("error", () => {
      if (!settled) {
        settled = true;
        sock.destroy();
        resolve(false);
      }
    });
  });
}

function findRepoRoot(explicit?: string): string | null {
  if (explicit) return isAbsolute(explicit) ? explicit : resolve(process.cwd(), explicit);
  // Walk up from cwd looking for the supervisor launcher.
  let dir = process.cwd();
  for (let i = 0; i < 8; i++) {
    if (existsSync(resolve(dir, "scripts", "run_runtime_supervisor.py")) && existsSync(resolve(dir, "studio-api", ".venv"))) {
      return dir;
    }
    const parent = resolve(dir, "..");
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

function venvPython(repoRoot: string): string | null {
  const win = resolve(repoRoot, "studio-api", ".venv", "Scripts", "python.exe");
  if (existsSync(win)) return win;
  const posix = resolve(repoRoot, "studio-api", ".venv", "bin", "python");
  if (existsSync(posix)) return posix;
  return null;
}

/**
 * Resolve append-mode log file paths for the supervisor's stdout/stderr.
 * Captures manager startup output (and any crash traceback) for diagnostics
 * instead of discarding it. Returns paths; the caller opens fds (posix) or
 * passes paths to Start-Process (Windows).
 */
function supervisorLogPaths(repoRoot: string, logDir?: string): { outPath: string; errPath: string } {
  const dir = logDir ? resolve(logDir) : resolve(repoRoot, "logs", "runtime", "bootstrap");
  try {
    mkdirSync(dir, { recursive: true });
  } catch {
    /* ignore — best effort */
  }
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  return {
    outPath: resolve(dir, `supervisor-${stamp}.out.log`),
    errPath: resolve(dir, `supervisor-${stamp}.err.log`),
  };
}

/**
 * Bring the Adept runtime online automatically. Idempotent and safe:
 * - If the control plane is already up, reuses it (warm) — never restarts.
 * - If down, spawns the canonical supervisor `serve` detached (no window).
 * Returns the supervisor child PID (when this process started it) or null.
 */
export async function startRuntimeBootstrap(opts: BootstrapOptions = {}): Promise<{
  supervisorPid: number | null;
  reused: boolean;
  collision?: boolean;
}> {
  const log = opts.log ?? ((m: string) => console.log(`[adept-runtime] ${m}`));
  opts.onEvent?.({ type: "checking" });

  if (await controlPlaneReachable(undefined, undefined, opts.probeTimeoutMs ?? 800)) {
    if (opts.reuseControlPlane === false) {
      const reason = "control plane :8759 is already open; not adopting or stopping it";
      opts.onEvent?.({ type: "failed", reason });
      log(reason);
      return { supervisorPid: null, reused: false, collision: true };
    }
    // Warm: manager already running — reuse, do NOT restart (Comfy leave-alone).
    opts.onEvent?.({ type: "reused" });
    log("control plane :8759 already online — reusing Background Services manager");
    return { supervisorPid: null, reused: true };
  }

  const explicitPy = opts.pythonPath && existsSync(opts.pythonPath) ? opts.pythonPath : null;
  const explicitLauncher = opts.launcherPath && existsSync(opts.launcherPath) ? opts.launcherPath : null;
  let repoRoot: string | null = opts.cwd || null;
  if (!explicitPy || !explicitLauncher) {
    repoRoot = findRepoRoot(opts.repoRoot);
    if (!repoRoot) {
      const reason = "repo root not found (scripts/run_runtime_supervisor.py + studio-api/.venv)";
      opts.onEvent?.({ type: "failed", reason });
      log(`failed: ${reason}`);
      return { supervisorPid: null, reused: false };
    }
  }
  const py = explicitPy || (repoRoot ? venvPython(repoRoot) : null);
  if (!py) {
    const reason = explicitPy ? "explicit python path missing" : "studio-api venv python not found";
    opts.onEvent?.({ type: "failed", reason });
    log(`failed: ${reason}`);
    return { supervisorPid: null, reused: false };
  }
  const launcher = explicitLauncher || (repoRoot ? resolve(repoRoot, "scripts", "run_runtime_supervisor.py") : "");
  if (!launcher || !existsSync(launcher)) {
    const reason = "run_runtime_supervisor.py not found";
    opts.onEvent?.({ type: "failed", reason });
    log(`failed: ${reason}`);
    return { supervisorPid: null, reused: false };
  }
  const cwd = opts.cwd || repoRoot || process.cwd();

  // Spawn the canonical supervisor `serve` detached (no console window on Windows).
  // It owns Studio API + headless Comfy as children and reuses a healthy Comfy.
  //
  // Robustness: the supervisor (serve_forever) ignores SIGBREAK on Windows, so stray
  // CTRL_BREAK console events no longer kill it with STATUS_CONTROL_C_EXIT during boot.
  // stdio is redirected to log files so any startup error is captured for diagnostics.
  const { outPath, errPath } = supervisorLogPaths(cwd, opts.logDir);
  const outFd = openSync(outPath, "a");
  const errFd = openSync(errPath, "a");
  const child = spawn(py, [launcher, "serve"], {
    cwd,
    detached: true,
    stdio: ["ignore", outFd, errFd],
    windowsHide: true,
    env: {
      ...process.env,
      ...(opts.extraEnv || {}),
      ...(opts.studioApiPort ? { ADEPT_STUDIO_API_PORT: String(opts.studioApiPort) } : {}),
      ADEPT_RUNTIME_BOOTSTRAPPED: "1",
    },
  });
  child.unref();
  _supervisorPid = child.pid ?? null;
  opts.onEvent?.({ type: "starting", supervisorPid: _supervisorPid ?? 0 });
  log(`spawning canonical supervisor (serve) pid=${_supervisorPid}`);

  // Detect a premature manager exit so we can fail fast instead of waiting 60s.
  // With the direct detached spawn, `child` IS the supervisor process, so its exit
  // before the control plane is up is a real failure (captures the exit code for
  // diagnostics; the traceback, if any, is in logs/runtime/bootstrap/).
  let childExited = false;
  let childExitCode: number | null = null;
  child.on("exit", (code, signal) => {
    childExited = true;
    childExitCode = code ?? -1;
    if (code !== 0 && code !== null) {
      log(`warning: supervisor pid=${_supervisorPid} exited code=${code} signal=${signal ?? ""} (see logs/runtime/bootstrap/)`);
    }
  });

  // Wait for the control plane to come up (manager starting → online).
  const deadline = Date.now() + 60_000;
  let online = false;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 1500));
    if (childExited) {
      const reason = `supervisor exited before binding :8759 (code=${childExitCode}) — see logs/runtime/bootstrap/`;
      opts.onEvent?.({ type: "failed", reason });
      log(`failed: ${reason}`);
      return { supervisorPid: _supervisorPid, reused: false };
    }
    if (await controlPlaneReachable(undefined, undefined, opts.probeTimeoutMs ?? 800)) {
      online = true;
      break;
    }
  }
  if (online) {
    opts.onEvent?.({ type: "online", managerPid: _supervisorPid ?? undefined });
    log("control plane online — Background Services manager ready");
  } else {
    opts.onEvent?.({ type: "failed", reason: "manager did not bind :8759 within 60s" });
    log("warning: manager did not bind :8759 within 60s (it may still be starting)");
  }
  return { supervisorPid: _supervisorPid, reused: false };
}

/** PID of the supervisor this process spawned (null if reused/none). */
export function getBootstrapSupervisorPid(): number | null {
  return _supervisorPid;
}
