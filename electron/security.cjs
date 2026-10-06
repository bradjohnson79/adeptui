"use strict";

const ALLOWED_CHANNELS = new Set([
  "adept:getInfo",
  "adept:getStatus",
  "adept:openExternal",
  "adept:selectUpdateArtifact",
]);

function classifyNavigation(rawUrl, { rendererOrigin, packaged }) {
  let url;
  try {
    url = new URL(rawUrl);
  } catch {
    return { action: "deny", reason: "invalid-url" };
  }
  if (rendererOrigin && url.origin === rendererOrigin) {
    return { action: "in-app", url: url.toString() };
  }
  if (url.protocol === "http:" && url.hostname === "127.0.0.1" && url.port === "5173") {
    if (packaged) return { action: "deny", reason: "vite-dev-server" };
    return { action: "in-app", url: url.toString() };
  }
  if (url.protocol === "http:" && url.hostname === "127.0.0.1") {
    return { action: "in-app", url: url.toString() };
  }
  if (url.protocol === "https:" || url.protocol === "http:") {
    return { action: "external", url: url.toString() };
  }
  return { action: "deny", reason: "scheme" };
}

function assertChannel(channel) {
  if (!ALLOWED_CHANNELS.has(channel)) {
    throw new Error(`IPC channel refused: ${channel}`);
  }
}

function isHttpUrl(value) {
  if (typeof value !== "string" || value.length > 4096) return false;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:";
  } catch {
    return false;
  }
}

module.exports = {
  ALLOWED_CHANNELS,
  classifyNavigation,
  assertChannel,
  isHttpUrl,
};
