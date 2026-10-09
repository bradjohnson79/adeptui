"use strict";

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("adeptDesktop", {
  getInfo: () => ipcRenderer.invoke("adept:getInfo"),
  getStatus: () => ipcRenderer.invoke("adept:getStatus"),
  openExternal: (url) => ipcRenderer.invoke("adept:openExternal", url),
  createDesktopShortcut: () => ipcRenderer.invoke("adept:createDesktopShortcut"),
  selectUpdateArtifact: (catalog) => ipcRenderer.invoke("adept:selectUpdateArtifact", catalog),
});
