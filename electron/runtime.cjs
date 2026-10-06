"use strict";

const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { listeningPids, commandLine, ownsPackagedCommand, portAccepts } = require("./platform/process.cjs");
const { userLayout, ensureUserDirs } = require("./platform/paths.cjs");
const { resolveStudioApiEndpoint, collisionMessage, CONTROL_PORT, COMFY_PORT } = require("./endpoint.cjs");

const DESKTOP_API = resolveStudioApiEndpoint("electron-packaged");

function packagedEnv(layout) {
  const keep = [
    "SystemRoot",
    "WINDIR",
    "PATH",
    "PATHEXT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "APPDATA",
    "LOCALAPPDATA",
    "USERNAME",
    "USERDOMAIN",
    "PROCESSOR_ARCHITECTURE",
    "NUMBER_OF_PROCESSORS",
    "OS",
    "ComSpec",
    "HOME",
    "LANG",
    "LC_ALL",
  ];
  const env = {};
  for (const key of keep) {
    if (process.env[key]) env[key] = process.env[key];
  }
  env.STUDIO_DATA_DIR = layout.dataDir;
  env.STUDIO_COMFY_INPUT_DIR = layout.comfyInput;
  env.STUDIO_COMFY_OUTPUT_DIR = layout.comfyOutput;
  env.STUDIO_COMFY_MODELS_DIR = layout.comfyModels;
  env.ADEPT_RUNTIME_HOME = layout.runtimeHome;
  env.ADEPT_RUNTIME_CONFIG = path.join(layout.runtimeHome, "runtime.json");
  env.PYTHONNOUSERSITE = "1";
  env.PYTHONDONTWRITEBYTECODE = "1";
  env.ADEPT_RUNTIME_MODE = DESKTOP_API.runtimeMode;
  env.ADEPT_STUDIO_API_PORT = String(DESKTOP_API.studioApiPort);
  env.ADEPT_RUNTIME_STATE_HOME = layout.runtimeHome;
  env.ADEPT_SUPERVISOR_STATE_DIR = supervisorStateDir(layout);
  env.ADEPT_RUNTIME_TOKEN_FILE = supervisorTokenFile(layout);
  env.ADEPT_COMFY_CONFIG_DIR = path.join(layout.runtimeHome, "comfy");
  return env;
}

function supervisorStateDir(layout) {
  return path.join(layout.runtimeHome, "supervisor");
}

function supervisorTokenFile(layout) {
  return path.join(supervisorStateDir(layout), "control.token");
}

function ownsBackgroundServices(cmd, markers) {
  const text = String(cmd || "").toLowerCase();
  if (!text.includes("runtime_supervisor")) return false;
  return ownsPackagedCommand(cmd, markers);
}

function classifyControlPlane(control, markers) {
  const commands = control && Array.isArray(control.commands) ? control.commands : [];
  if (!control || !control.open) return { action: "start", collision: false, owned: false };
  const owned = commands.some((row) => ownsBackgroundServices(row.command, markers));
  if (owned) return { action: "reuse", collision: false, owned: true };
  return { action: "leave", collision: true, owned: false };
}

function writePackagedRuntimeConfig(layout, pythonPath, apiSource) {
  const file = path.join(layout.runtimeHome, "runtime.json");
  if (fs.existsSync(file)) return file;
  const stateDir = supervisorStateDir(layout);
  fs.mkdirSync(stateDir, { recursive: true });
  fs.mkdirSync(path.join(layout.runtimeHome, "comfy"), { recursive: true });
  const config = {
    comfyRoot: "",
    comfyPython: "",
    modelRoot: layout.comfyModels,
    port: COMFY_PORT,
    controlPort: CONTROL_PORT,
    logDir: layout.logs,
    stateDir,
    servicePython: pythonPath,
    repoRoot: "",
    autostart: false,
    studioApi: {
      enabled: false,
      python: pythonPath,
      appRoot: apiSource,
      port: 8758,
    },
  };
  fs.writeFileSync(file, JSON.stringify(config, null, 2));
  return file;
}

function readControlStatus(tokenFile) {
  return new Promise((resolve) => {
    let token = "";
    try {
      token = fs.readFileSync(tokenFile, "utf8").trim();
    } catch {
      resolve({ status: 0, body: "" });
      return;
    }
    if (!token) {
      resolve({ status: 0, body: "" });
      return;
    }
    const req = http.request(
      {
        host: "127.0.0.1",
        port: CONTROL_PORT,
        path: "/status",
        method: "GET",
        headers: { "X-Adept-Runtime-Token": token, Accept: "application/json" },
      },
      (res) => {
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => resolve({ status: res.statusCode || 0, body: Buffer.concat(chunks).toString("utf8") }));
      },
    );
    req.on("error", () => resolve({ status: 0, body: "" }));
    req.setTimeout(1500, () => {
      req.destroy();
      resolve({ status: 0, body: "" });
    });
    req.end();
  });
}

async function waitForBackgroundServices(tokenFile, timeoutMs = 25000) {
  const deadline = Date.now() + timeoutMs;
  let last = { status: 0, body: "" };
  while (Date.now() < deadline) {
    last = await readControlStatus(tokenFile);
    if (last.status === 200 && /"ok"\s*:\s*true/.test(last.body)) return { healthy: true, ...last };
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  return { healthy: false, ...last };
}

async function inspectPort(port) {
  const open = await portAccepts(port);
  if (!open) return { port, open: false, pids: [], commands: [] };
  const pids = await listeningPids(port);
  const commands = [];
  for (const pid of pids) {
    commands.push({ pid, command: await commandLine(pid) });
  }
  return { port, open: true, pids, commands };
}

/**
 * Packaged launch. Studio API stays on 8760. Background Services is the
 * existing runtime_supervisor serve owner on 8759. Comfy stays optional:
 * an empty runtime config does not spawn it. A foreign listener on 8760
 * or 8759 is left alone.
 */
async function preparePackagedApi({ pythonPath, apiSource, userData }) {
  const layout = userLayout(userData);
  const port = DESKTOP_API.studioApiPort;
  ensureUserDirs(layout);
  writePackagedRuntimeConfig(layout, pythonPath, apiSource);
  const [api, control, comfy] = await Promise.all([
    inspectPort(port),
    inspectPort(CONTROL_PORT),
    inspectPort(COMFY_PORT),
  ]);
  const markers = [pythonPath, apiSource];
  const owned = api.commands.some((row) => ownsPackagedCommand(row.command, markers));
  const controlPlan = classifyControlPlane(control, markers);
  const status = {
    api,
    control,
    comfy,
    spawned: false,
    owned,
    collision: false,
    childPid: null,
    dataDir: layout.dataDir,
    backgroundServices: {
      spawned: false,
      owned: controlPlan.owned,
      collision: controlPlan.collision,
      healthy: false,
      pid: null,
      command: "",
    },
  };
  let supervisorChild = null;
  if (controlPlan.collision) {
    status.backgroundServices.reason = collisionMessage(CONTROL_PORT);
  } else if (controlPlan.owned) {
    const ownedRow = (control.commands || []).find((row) => ownsBackgroundServices(row.command, markers));
    status.backgroundServices.reason = "Background Services already running";
    status.backgroundServices.pid = ownedRow ? ownedRow.pid : null;
    status.backgroundServices.command = ownedRow ? ownedRow.command : "";
    status.backgroundServices.healthy = true;
  } else if (fs.existsSync(pythonPath)) {
    const logPath = path.join(layout.logs, "background-services.log");
    const logFd = fs.openSync(logPath, "a");
    const args = ["-m", "runtime_supervisor", "serve"];
    supervisorChild = spawn(pythonPath, args, {
      cwd: apiSource,
      env: packagedEnv(layout),
      windowsHide: true,
      stdio: ["ignore", logFd, logFd],
    });
    status.backgroundServices.spawned = true;
    status.backgroundServices.owned = true;
    status.backgroundServices.pid = supervisorChild.pid || null;
    status.backgroundServices.command = `${pythonPath} -m runtime_supervisor serve`;
    const ready = await waitForBackgroundServices(supervisorTokenFile(layout));
    status.backgroundServices.healthy = ready.healthy;
    status.backgroundServices.reason = ready.healthy ? "Background Services is healthy" : "Background Services did not become healthy";
  } else {
    status.backgroundServices.reason = "packaged Python runtime is missing";
  }
  if (api.open && !owned) {
    status.collision = true;
    status.reason = collisionMessage(port);
    status.diagnostics = api.commands;
    return { status, child: null, supervisorChild, layout };
  }
  if (owned) {
    status.reason = "packaged Studio API already running";
    return { status, child: null, supervisorChild, layout };
  }
  if (!fs.existsSync(pythonPath)) {
    status.collision = false;
    status.reason = "packaged Python runtime is missing";
    status.setupRequired = true;
    return { status, child: null, supervisorChild, layout };
  }
  const logPath = path.join(layout.logs, "studio-api.log");
  const logFd = fs.openSync(logPath, "a");
  const child = spawn(pythonPath, ["-m", "uvicorn", "app.main:app", "--host", DESKTOP_API.studioApiHost, "--port", String(port)], {
    cwd: apiSource,
    env: packagedEnv(layout),
    windowsHide: true,
    stdio: ["ignore", logFd, logFd],
  });
  status.spawned = true;
  status.childPid = child.pid || null;
  status.command = `${pythonPath} -m uvicorn app.main:app --host ${DESKTOP_API.studioApiHost} --port ${port}`;
  status.endpoint = DESKTOP_API;
  status.reason = "spawned packaged Studio API";
  return { status, child, supervisorChild, layout };
}

module.exports = {
  DESKTOP_API,
  CONTROL_PORT,
  COMFY_PORT,
  packagedEnv,
  preparePackagedApi,
  inspectPort,
  classifyControlPlane,
  ownsBackgroundServices,
  writePackagedRuntimeConfig,
};
