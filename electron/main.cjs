"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { app, BrowserWindow, ipcMain, shell, screen } = require("electron");
const { readDesktopVersion, packagedLayout, pathTouchesDevRepo } = require("./platform/paths.cjs");
const { buildMenu } = require("./platform/menu.cjs");
const { classifyNavigation, isHttpUrl } = require("./security.cjs");
const { selectDesktopArtifact } = require("./update/bridge.cjs");
const { preparePackagedApi, DESKTOP_API } = require("./runtime.cjs");
const { collisionMessage } = require("./endpoint.cjs");
const { portAccepts } = require("./platform/process.cjs");
const { startRendererServer } = require("./renderer-server.cjs");

const DEV_REPO = path.resolve(__dirname, "..");
const identity = readDesktopVersion(process.resourcesPath, __dirname);
const packaged = app.isPackaged;

let mainWindow = null;
let rendererServer = null;
let apiChild = null;
let supervisorChild = null;
let desktopStatus = {
  packaged,
  version: identity.version,
  platform: process.platform,
  arch: process.arch,
  viteContacted: false,
  apiOwned: false,
  collision: false,
  rendererOrigin: null,
  paths: {},
  endpoint: packaged ? DESKTOP_API : null,
  proxy: { api: 0, media: 0, targetPort: packaged ? DESKTOP_API.studioApiPort : null },
};

function boundsFile() {
  return path.join(app.getPath("userData"), "window-bounds.json");
}

function statusFile() {
  return path.join(app.getPath("userData"), "desktop-status.json");
}

function writeStatus() {
  try {
    fs.mkdirSync(app.getPath("userData"), { recursive: true });
    fs.writeFileSync(statusFile(), JSON.stringify(desktopStatus, null, 2));
  } catch {
    /* status is best-effort */
  }
}

function loadBounds() {
  try {
    const parsed = JSON.parse(fs.readFileSync(boundsFile(), "utf8"));
    const displays = screen.getAllDisplays();
    const visible = displays.some((display) => {
      const area = display.workArea;
      const cx = parsed.x + Math.min(parsed.width, 80);
      const cy = parsed.y + Math.min(parsed.height, 80);
      return cx >= area.x && cy >= area.y && cx < area.x + area.width && cy < area.y + area.height;
    });
    if (!visible) return null;
    return parsed;
  } catch {
    return null;
  }
}

function rememberBounds(win) {
  if (!win || win.isDestroyed()) return;
  const bounds = win.getBounds();
  fs.mkdirSync(path.dirname(boundsFile()), { recursive: true });
  fs.writeFileSync(boundsFile(), JSON.stringify(bounds));
}

function attachNavigation(win, rendererOrigin) {
  const decide = (raw) => classifyNavigation(raw, { rendererOrigin, packaged });
  win.webContents.setWindowOpenHandler(({ url }) => {
    const choice = decide(url);
    if (choice.action === "external") {
      shell.openExternal(choice.url);
      return { action: "deny" };
    }
    if (choice.action === "in-app") return { action: "allow" };
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (event, url) => {
    const choice = decide(url);
    if (choice.action === "in-app" && (!rendererOrigin || url.startsWith(rendererOrigin) || (!packaged && url.startsWith("http://127.0.0.1:5173")))) {
      return;
    }
    event.preventDefault();
    if (choice.action === "external") shell.openExternal(choice.url);
  });
}

function createWindow(startUrl) {
  const saved = loadBounds();
  const win = new BrowserWindow({
    width: saved?.width || 1440,
    height: saved?.height || 900,
    x: saved?.x,
    y: saved?.y,
    show: false,
    backgroundColor: "#070b14",
    title: identity.productName || "Adept UI",
    autoHideMenuBar: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
    },
  });
  win.once("ready-to-show", () => win.show());
  const persist = () => rememberBounds(win);
  win.on("resize", persist);
  win.on("move", persist);
  win.loadURL(startUrl);
  return win;
}

async function startDev() {
  const bootstrapBuild = path.join(__dirname, "build", "compiled", "bootstrap.cjs");
  if (fs.existsSync(bootstrapBuild)) {
    const { startRuntimeBootstrap } = require(bootstrapBuild);
    await startRuntimeBootstrap({
      repoRoot: DEV_REPO,
      reuseControlPlane: true,
      log: (msg) => console.log(msg),
    });
  }
  const viteUp = await portAccepts(5173);
  desktopStatus.viteContacted = viteUp;
  if (!viteUp) {
    desktopStatus.reason = "Vite is not running on 127.0.0.1:5173. Start the web workflow, then reopen Adept UI.";
    writeStatus();
    mainWindow = createWindow("about:blank");
    attachNavigation(mainWindow, null);
    await mainWindow.loadURL(`data:text/html,${encodeURIComponent("<body style='background:#070b14;color:#f5f7fb;font-family:sans-serif;padding:32px'><h1>Adept UI</h1><p>The local creator UI is not running. Start it, then reopen this window.</p></body>")}`);
    return;
  }
  desktopStatus.rendererOrigin = "http://127.0.0.1:5173";
  desktopStatus.apiOwned = false;
  writeStatus();
  mainWindow = createWindow("http://127.0.0.1:5173/");
  attachNavigation(mainWindow, "http://127.0.0.1:5173");
}

async function startPackaged() {
  const layout = packagedLayout(process.resourcesPath);
  const prepared = await preparePackagedApi({
    pythonPath: layout.python,
    apiSource: layout.apiSource,
    userData: app.getPath("userData"),
  });
  apiChild = prepared.child;
  supervisorChild = prepared.supervisorChild || null;
  if (supervisorChild) {
    supervisorChild.on("exit", () => {
      if (desktopStatus.backgroundServices) {
        desktopStatus.backgroundServices.spawned = false;
        desktopStatus.backgroundServices.healthy = false;
      }
      writeStatus();
    });
  }
  if (apiChild) {
    apiChild.on("exit", (code) => {
      desktopStatus.apiOwned = false;
      desktopStatus.apiExited = true;
      desktopStatus.apiExitCode = code;
      writeStatus();
    });
  }
  desktopStatus.collision = prepared.status.collision;
  desktopStatus.apiOwned = Boolean(prepared.status.spawned || prepared.status.owned);
  desktopStatus.apiCommand = prepared.status.command || null;
  desktopStatus.reason = prepared.status.reason || "";
  desktopStatus.setupRequired = Boolean(prepared.status.setupRequired);
  desktopStatus.backgroundServices = prepared.status.backgroundServices || null;
  if (desktopStatus.backgroundServices && desktopStatus.backgroundServices.port) {
    desktopStatus.endpoint = { ...DESKTOP_API, controlPort: desktopStatus.backgroundServices.port };
  }
  desktopStatus.ports = {
    api: prepared.status.api,
    control: prepared.status.control,
    comfy: prepared.status.comfy,
  };
  desktopStatus.viteContacted = false;
  const devRepoHit = [layout.python, layout.apiSource, layout.renderer, prepared.layout.dataDir, prepared.layout.logs].some((item) =>
    pathTouchesDevRepo(item, DEV_REPO),
  );
  desktopStatus.paths = {
    renderer: layout.renderer,
    python: layout.python,
    apiSource: layout.apiSource,
    logs: prepared.layout.logs,
    userData: prepared.layout.userData,
    temp: prepared.layout.temp,
    dataDir: prepared.layout.dataDir,
    resources: process.resourcesPath,
    devRepoPathDependency: devRepoHit ? 1 : 0,
  };
  rendererServer = await startRendererServer({
    rendererRoot: layout.renderer,
    apiPort: DESKTOP_API.studioApiPort,
    allowApi: () => desktopStatus.apiOwned && !desktopStatus.collision && !desktopStatus.apiExited,
    blockedMessage: collisionMessage(DESKTOP_API.studioApiPort),
    onProxy: (kind, targetPort) => {
      desktopStatus.proxy.targetPort = targetPort;
      desktopStatus.proxy[kind] = (desktopStatus.proxy[kind] || 0) + 1;
      writeStatus();
    },
  });
  if (rendererServer.port === 5173) throw new Error("refusing Vite port for the packaged renderer");
  desktopStatus.rendererOrigin = rendererServer.origin;
  writeStatus();
  mainWindow = createWindow(`${rendererServer.origin}/`);
  attachNavigation(mainWindow, rendererServer.origin);
  mainWindow.webContents.session.webRequest.onBeforeRequest(
    { urls: ["*://fonts.googleapis.com/*", "*://fonts.gstatic.com/*"] },
    (_details, callback) => callback({ cancel: true }),
  );
}

function registerIpc() {
  ipcMain.handle("adept:getInfo", () => ({
    version: identity.version,
    productName: identity.productName,
    appId: identity.appId,
    platform: process.platform,
    arch: process.arch,
    packaged,
  }));
  ipcMain.handle("adept:getStatus", () => desktopStatus);
  ipcMain.handle("adept:createDesktopShortcut", () => {
    const { createDesktopShortcut, recordShortcut } = require("./desktopShortcut.cjs");
    const result = createDesktopShortcut(process.execPath);
    if (result && result.path) {
      const record = recordShortcut(path.join(app.getPath("userData"), "desktop-shortcut.json"), result.path);
      result.recorded = Boolean(record.recorded);
    }
    return result;
  });
  ipcMain.handle("adept:openExternal", (_event, url) => {
    if (!isHttpUrl(url)) return { ok: false };
    const choice = classifyNavigation(url, { rendererOrigin: desktopStatus.rendererOrigin, packaged });
    if (choice.action !== "external") return { ok: false };
    return shell.openExternal(choice.url).then(() => ({ ok: true }));
  });
  ipcMain.handle("adept:selectUpdateArtifact", (_event, catalog) => {
    if (!catalog || typeof catalog !== "object" || Array.isArray(catalog)) {
      return { ok: false, code: "INVALID_CATALOG", selected: null };
    }
    return selectDesktopArtifact(catalog, {
      platform: process.platform,
      arch: process.arch,
      installedVersion: identity.version,
    });
  });
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
  app.whenReady().then(async () => {
    app.setAppUserModelId(identity.appId);
    buildMenu({ productName: identity.productName || "Adept UI", onQuit: () => app.quit() });
    registerIpc();
    if (packaged) await startPackaged();
    else await startDev();
  });
  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
  });
  app.on("before-quit", () => {
    writeStatus();
    if (rendererServer) rendererServer.server.close();
    const stopOwned = (child) => {
      if (!child || child.exitCode !== null || child.killed) return;
      try {
        child.kill(process.platform === "darwin" ? "SIGKILL" : undefined);
      } catch {
        /* the owned process already exited */
      }
    };
    stopOwned(apiChild);
    stopOwned(supervisorChild);
  });
}
