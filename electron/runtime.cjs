"use strict";

const fs = require("node:fs");
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
  const tokenFile = existingSupervisorToken();
  if (tokenFile) env.ADEPT_RUNTIME_TOKEN_FILE = tokenFile;
  return env;
}

function existingSupervisorToken() {
  const appdata = process.env.APPDATA;
  if (!appdata) return "";
  try {
    const cfg = JSON.parse(fs.readFileSync(path.join(appdata, "Adept", "Runtime", "runtime.json"), "utf8"));
    const stateDir = typeof cfg.stateDir === "string" ? cfg.stateDir : "";
    const token = stateDir ? path.join(stateDir, "control.token") : "";
    return token && fs.existsSync(token) ? token : "";
  } catch {
    return "";
  }
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
 * Packaged API launch. Does not call the runtime supervisor, because
 * serve_forever also calls Comfy request_start. Does not kill a foreign
 * listener on 8760, 8759, or 8188. It does not bind 8758.
 */
async function preparePackagedApi({ pythonPath, apiSource, userData }) {
  const layout = userLayout(userData);
  const port = DESKTOP_API.studioApiPort;
  ensureUserDirs(layout);
  const [api, control, comfy] = await Promise.all([
    inspectPort(port),
    inspectPort(CONTROL_PORT),
    inspectPort(COMFY_PORT),
  ]);
  const markers = [pythonPath, apiSource];
  const owned = api.commands.some((row) => ownsPackagedCommand(row.command, markers));
  const status = {
    api,
    control,
    comfy,
    spawned: false,
    owned,
    collision: false,
    childPid: null,
    dataDir: layout.dataDir,
  };
  if (api.open && !owned) {
    status.collision = true;
    status.reason = collisionMessage(port);
    status.diagnostics = api.commands;
    return { status, child: null, layout };
  }
  if (owned) {
    status.reason = "packaged Studio API already running";
    return { status, child: null, layout };
  }
  if (!fs.existsSync(pythonPath)) {
    status.collision = false;
    status.reason = "packaged Python runtime is missing";
    status.setupRequired = true;
    return { status, child: null, layout };
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
  return { status, child, layout };
}

module.exports = {
  DESKTOP_API,
  CONTROL_PORT,
  COMFY_PORT,
  packagedEnv,
  preparePackagedApi,
  inspectPort,
};
