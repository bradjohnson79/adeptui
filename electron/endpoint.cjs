"use strict";

/**
 * One Studio API endpoint owner for the desktop shell.
 * Web development and Electron development stay on 8758 because Electron
 * development loads Vite, and Vite already proxies to the dev API.
 * Electron packaged mode is the only mode that binds 8760.
 * Comfy stays 8188. Background Services stay 8759.
 * This port is runtime configuration. It is not written into project data.
 */

const HOST = "127.0.0.1";
const DEV_STUDIO_API_PORT = 8758;
const DESKTOP_STUDIO_API_PORT = 8760;
const CONTROL_PORT = 8759;
const COMFY_PORT = 8188;
const VITE_PORT = 5173;

const MODES = new Set(["web-development", "electron-development", "electron-packaged"]);

function resolveStudioApiEndpoint(mode) {
  if (!MODES.has(mode)) {
    throw new Error(`Unknown runtime mode: ${mode}`);
  }
  const studioApiPort = mode === "electron-packaged" ? DESKTOP_STUDIO_API_PORT : DEV_STUDIO_API_PORT;
  return {
    studioApiHost: HOST,
    studioApiPort,
    studioApiBaseUrl: `http://${HOST}:${studioApiPort}`,
    runtimeMode: mode,
    controlPort: CONTROL_PORT,
    comfyPort: COMFY_PORT,
    vitePort: VITE_PORT,
  };
}

function collisionMessage(port) {
  return `Adept UI could not start because local port ${port} is already in use.`;
}

module.exports = {
  DEV_STUDIO_API_PORT,
  DESKTOP_STUDIO_API_PORT,
  CONTROL_PORT,
  COMFY_PORT,
  VITE_PORT,
  resolveStudioApiEndpoint,
  collisionMessage,
};
