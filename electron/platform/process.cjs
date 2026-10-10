"use strict";

const { execFile } = require("node:child_process");
const net = require("node:net");

function portAccepts(port, host = "127.0.0.1", timeoutMs = 800) {
  return new Promise((resolve) => {
    let settled = false;
    const sock = net.connect({ host, port }, () => {
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
        resolve(false);
      }
    });
  });
}

function execText(file, args) {
  return new Promise((resolve) => {
    execFile(file, args, { windowsHide: true, timeout: 8000, maxBuffer: 4 * 1024 * 1024 }, (err, stdout) => {
      if (err) resolve("");
      else resolve(String(stdout || ""));
    });
  });
}

function parseSsListenPids(text) {
  const pids = [];
  for (const match of String(text || "").matchAll(/pid=(\d+)/g)) {
    const pid = Number(match[1]);
    if (Number.isInteger(pid) && pid > 0 && !pids.includes(pid)) pids.push(pid);
  }
  return pids;
}

function parseListeningPids(netstatText, port) {
  const pids = new Set();
  const needle = `:${port}`;
  for (const line of String(netstatText).split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || !/\bLISTENING\b/i.test(trimmed)) continue;
    if (!trimmed.includes(needle)) continue;
    const parts = trimmed.split(/\s+/);
    const pid = Number(parts[parts.length - 1]);
    if (Number.isInteger(pid) && pid > 0) pids.add(pid);
  }
  return [...pids];
}

async function listeningPids(port) {
  if (process.platform === "win32") {
    const text = await execText("netstat.exe", ["-ano", "-p", "tcp"]);
    return parseListeningPids(text, port);
  }
  const fromSs = parseSsListenPids(await execText("ss", ["-ltnpH", `sport = :${port}`]));
  if (fromSs.length) return fromSs;
  const text = await execText("lsof", ["-nP", `-iTCP:${port}`, "-sTCP:LISTEN", "-t"]);
  return text
    .split(/\s+/)
    .map((s) => Number(s))
    .filter((n) => Number.isInteger(n) && n > 0);
}

async function commandLine(pid) {
  const id = Number(pid);
  if (!Number.isInteger(id) || id <= 0) return "";
  if (process.platform === "win32") {
    const script = `(Get-CimInstance Win32_Process -Filter "ProcessId=${id}").CommandLine`;
    return (await execText("powershell.exe", ["-NoProfile", "-NonInteractive", "-Command", script])).trim();
  }
  return (await execText("ps", ["-p", String(id), "-o", "args="])).trim();
}

function ownsPackagedCommand(cmd, markers) {
  const text = String(cmd || "").toLowerCase();
  return markers.some((m) => m && text.includes(String(m).toLowerCase()));
}

module.exports = {
  portAccepts,
  parseListeningPids,
  parseSsListenPids,
  listeningPids,
  commandLine,
  ownsPackagedCommand,
};
