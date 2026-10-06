/**
 * One packaged dependency definition: electron/packaged-requirements.txt.
 * Platform selection uses PEP 508 environment markers. Do not keep a second
 * hand-maintained requirements list.
 */

import fs from "node:fs";
import path from "node:path";

export function stripRequirementComment(line) {
  let quote = "";
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (quote) {
      if (ch === quote) quote = "";
      continue;
    }
    if (ch === '"' || ch === "'") {
      quote = ch;
      continue;
    }
    if (ch === "#") return line.slice(0, i);
  }
  return line;
}

export function markerMatches(marker, sysPlatform) {
  const text = String(marker || "").trim();
  if (!text) return true;
  const parts = text.split(/\s+and\s+/i);
  return parts.every((part) => {
    const match = part.trim().match(/^sys_platform\s*(==|!=)\s*["']([A-Za-z0-9_]+)["']$/);
    if (!match) {
      throw new Error(`Unsupported packaged requirement marker: ${text}`);
    }
    const equals = match[1] === "==";
    const expected = match[2];
    return equals ? sysPlatform === expected : sysPlatform !== expected;
  });
}

export function parsePackagedRequirements(text) {
  const rows = [];
  for (const line of String(text).split(/\r?\n/)) {
    const code = stripRequirementComment(line).trim();
    if (!code) continue;
    const splitAt = code.indexOf(";");
    const requirement = (splitAt === -1 ? code : code.slice(0, splitAt)).trim();
    const marker = splitAt === -1 ? "" : code.slice(splitAt + 1).trim();
    const nameMatch = requirement.match(/^[A-Za-z0-9_.-]+/);
    if (!nameMatch) throw new Error(`Cannot read requirement name: ${code}`);
    rows.push({
      name: nameMatch[0].toLowerCase().replaceAll("_", "-"),
      requirement,
      marker,
      raw: code,
    });
  }
  return rows;
}

export function selectRequirements(text, sysPlatform) {
  const selected = [];
  const skipped = [];
  for (const row of parsePackagedRequirements(text)) {
    const on = markerMatches(row.marker, sysPlatform);
    (on ? selected : skipped).push({ ...row, selected: on });
  }
  return { selected, skipped };
}

export function pywin32InstallPlan(text) {
  const windows = selectRequirements(text, "win32").selected.filter((row) => row.name === "pywin32");
  const macos = selectRequirements(text, "darwin").selected.filter((row) => row.name === "pywin32");
  const linux = selectRequirements(text, "linux").selected.filter((row) => row.name === "pywin32");
  return {
    windowsPresent: windows.some((row) => row.requirement.includes("==312")),
    macosInstallAttempts: macos.length,
    linuxInstallAttempts: linux.length,
  };
}

export function renderSelectedRequirements(text, sysPlatform) {
  const { selected } = selectRequirements(text, sysPlatform);
  const body = selected.map((row) => row.raw).join("\n");
  return `# Generated from electron/packaged-requirements.txt for sys_platform == "${sysPlatform}".\n# Do not edit. The authoritative pin file is the only maintained list.\n${body}\n`;
}

const WINDOWS_BINARY = /\.(exe|dll|pyd)$/i;

export function auditPackagedTree(rootDir, options = {}) {
  const rejectMac = Boolean(options.rejectMac);
  const problems = [];
  if (!rootDir || !fs.existsSync(rootDir)) {
    problems.push(`missing ${rootDir}`);
    return problems;
  }
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      const name = entry.name.toLowerCase();
      const ctypes = name.startsWith("pywin32_ctypes") || name.startsWith("pywin32-ctypes");
      if (entry.isDirectory()) {
        if (!ctypes && (name === "pywin32" || name.startsWith("pywin32-"))) problems.push(full);
        walk(full);
        continue;
      }
      if (!ctypes && (WINDOWS_BINARY.test(entry.name) || name.includes("win_amd64"))) {
        problems.push(full);
      }
      if (rejectMac && name.endsWith(".dylib")) problems.push(full);
      if (entry.name === "WHEEL") {
        const body = fs.readFileSync(full, "utf8");
        if (/\bwin_amd64\b/.test(body) || /\bwin32\b/.test(body)) problems.push(full);
        if (rejectMac && /macosx/.test(body)) problems.push(full);
      }
    }
  };
  walk(rootDir);
  return problems;
}
