"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

const SHORTCUT_NAME = "Adept UI";

function desktopDir() {
  if (process.platform === "win32") {
    const fromEnv = process.env.USERPROFILE
      ? path.join(process.env.USERPROFILE, "Desktop")
      : path.join(os.homedir(), "Desktop");
    return fs.existsSync(fromEnv) ? fromEnv : path.join(os.homedir(), "Desktop");
  }
  const unix = path.join(os.homedir(), "Desktop");
  return unix;
}

function shortcutPath() {
  if (process.platform === "win32") return path.join(desktopDir(), `${SHORTCUT_NAME}.lnk`);
  if (process.platform === "darwin") return path.join(desktopDir(), `${SHORTCUT_NAME} alias`);
  return path.join(desktopDir(), `${SHORTCUT_NAME}.desktop`);
}

function linuxDesktopEntry(execPath) {
  const quoted = `"${String(execPath).replace(/"/g, '\\"')}"`;
  return [
    "[Desktop Entry]",
    "Type=Application",
    "Name=Adept UI",
    "Comment=Add an Adept UI icon to your desktop for quick access.",
    `Exec=${quoted}`,
    "Icon=Adept UI",
    "Terminal=false",
    "Categories=Video;",
    "",
  ].join("\n");
}

function recordShortcut(recordFile, shortcutFile) {
  const destination = String(shortcutFile || "");
  if (!destination || path.basename(destination).indexOf(SHORTCUT_NAME) !== 0) {
    return { ok: false, recorded: false, message: "Only an Adept UI shortcut path can be recorded." };
  }
  fs.mkdirSync(path.dirname(recordFile), { recursive: true });
  const payload = { path: destination, name: SHORTCUT_NAME };
  fs.writeFileSync(recordFile, JSON.stringify(payload), "utf8");
  return { ok: true, recorded: true, path: destination };
}

function removeRecordedShortcut(recordFile) {
  if (!recordFile || !fs.existsSync(recordFile)) {
    return { ok: true, removed: false, message: "No Adept UI desktop shortcut was recorded." };
  }
  let record;
  try {
    record = JSON.parse(fs.readFileSync(recordFile, "utf8"));
  } catch {
    return { ok: false, removed: false, message: "The shortcut record could not be read. Nothing was deleted." };
  }
  const target = String(record.path || "");
  if (!target || path.basename(target).indexOf(SHORTCUT_NAME) !== 0) {
    return { ok: false, removed: false, message: "The recorded path is not an Adept UI shortcut. It was left in place." };
  }
  if (fs.existsSync(target)) fs.unlinkSync(target);
  fs.unlinkSync(recordFile);
  return { ok: true, removed: true, path: target };
}

function createDesktopShortcut(execPath) {
  const target = String(execPath || "").trim();
  if (!target) {
    return { ok: false, created: false, message: "The installed Adept UI application was not found. Setup can continue." };
  }
  const destination = shortcutPath();
  if (fs.existsSync(destination)) {
    return { ok: true, created: false, path: destination, message: "The Adept UI desktop shortcut is already there." };
  }
  try {
    fs.mkdirSync(path.dirname(destination), { recursive: true });
    if (process.platform === "win32") {
      const script = [
        "$shell = New-Object -ComObject WScript.Shell",
        `$shortcut = $shell.CreateShortcut(${JSON.stringify(destination)})`,
        `$shortcut.TargetPath = ${JSON.stringify(target)}`,
        "$shortcut.WorkingDirectory = [System.IO.Path]::GetDirectoryName($shortcut.TargetPath)",
        "$shortcut.IconLocation = $shortcut.TargetPath",
        "$shortcut.Description = 'Adept UI'",
        "$shortcut.Save()",
      ].join("; ");
      const result = spawnSync("powershell.exe", ["-NoProfile", "-Command", script], { windowsHide: true, encoding: "utf8" });
      if (result.status !== 0 || !fs.existsSync(destination)) {
        return { ok: false, created: false, message: "Windows could not create the desktop shortcut. Adept UI is still installed." };
      }
    } else if (process.platform === "darwin") {
      const script = `tell application "Finder" to make alias file to POSIX file ${JSON.stringify(target)} at POSIX file ${JSON.stringify(desktopDir())}`;
      const result = spawnSync("osascript", ["-e", script], { encoding: "utf8" });
      if (result.status !== 0) {
        return { ok: false, created: false, message: "macOS could not create a desktop alias. The application remains in Applications." };
      }
    } else {
      fs.writeFileSync(destination, linuxDesktopEntry(target), "utf8");
      try {
        fs.chmodSync(destination, 0o755);
      } catch {
        /* permissions are reported, not fatal */
      }
      spawnSync("gio", ["set", destination, "metadata::trusted", "true"], { encoding: "utf8" });
    }
  } catch (error) {
    return {
      ok: false,
      created: false,
      message: error instanceof Error ? error.message : "The desktop did not accept the shortcut. Adept UI can still start.",
    };
  }
  return {
    ok: fs.existsSync(destination),
    created: fs.existsSync(destination),
    path: destination,
    message: fs.existsSync(destination)
      ? "Adept UI was added to the desktop."
      : "The desktop did not accept the shortcut. Adept UI can still start.",
  };
}

module.exports = {
  SHORTCUT_NAME,
  shortcutPath,
  linuxDesktopEntry,
  recordShortcut,
  removeRecordedShortcut,
  createDesktopShortcut,
};
