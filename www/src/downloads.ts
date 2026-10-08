/**
 * Public download configuration.
 * Every download control reads this record. Addresses are the published
 * GitHub release assets for Adept UI 1.1.1 Beta.
 * The page never reads a download address from the query string.
 */

export type DesktopOs = "windows" | "macos" | "linux";
export type ClientOs = DesktopOs | "ios" | "android" | "unknown";
export type CpuArch = "x64" | "arm64";

export type OsSignals = {
  userAgentDataPlatform?: string | null;
  platform?: string | null;
  userAgent?: string | null;
};

/** A future architecture-specific installer. Hidden until `available` is true. */
export type ReleaseBuild = {
  architecture: CpuArch;
  label: string;
  url: string;
  available: boolean;
  installerType?: string;
  audience?: string;
  detail?: string;
  fileSize?: string;
  releaseDate?: string;
};

export type PlatformRelease = {
  id: DesktopOs;
  label: string;
  /** Verified public version only. Omit until a release exists. */
  version?: string;
  url: string;
  available: boolean;
  builds: ReleaseBuild[];
};

export const desktopPlatforms: DesktopOs[] = ["windows", "macos", "linux"];

const releaseBase = "https://github.com/bradjohnson79/adeptui/releases/download/v1.1.1";

function releaseUrl(fileName: string): string {
  return `${releaseBase}/${encodeURIComponent(fileName)}`;
}

const windowsInstaller = releaseUrl("Adept.UI-Setup-1.1.1-win-x64.exe");
const macInstaller = releaseUrl("Adept.UI-1.1.1-mac-arm64.dmg");
const linuxDeb = releaseUrl("Adept.UI-1.1.1-linux-x64.deb");
const linuxRpm = releaseUrl("Adept.UI-1.1.1-linux-x64.rpm");
const linuxAppImage = releaseUrl("Adept.UI-1.1.1-linux-x64.AppImage");

/** Generic Linux detection opens this chooser. It is not a file download. */
export const linuxPackageChooserHref = "#linux-packages";

export const downloads: Record<DesktopOs, PlatformRelease> = {
  windows: {
    id: "windows",
    label: "Windows Beta",
    version: "1.1.1",
    url: windowsInstaller,
    available: true,
    builds: [],
  },
  macos: {
    id: "macos",
    label: "macOS Beta",
    version: "1.1.1",
    url: macInstaller,
    available: true,
    builds: [],
  },
  linux: {
    id: "linux",
    label: "Linux Beta",
    version: "1.1.1",
    url: "",
    available: true,
    builds: [
      {
        architecture: "x64",
        label: "Download .deb",
        audience: "Ubuntu / Debian",
        detail: "Recommended for Ubuntu, Debian, Linux Mint, and Pop!_OS",
        url: linuxDeb,
        available: true,
        installerType: "deb",
      },
      {
        architecture: "x64",
        label: "Download .rpm",
        audience: "Fedora / RHEL",
        detail: "Recommended for Fedora and compatible RPM-based distributions",
        url: linuxRpm,
        available: true,
        installerType: "rpm",
      },
      {
        architecture: "x64",
        label: "Download AppImage",
        audience: "Universal Linux",
        detail: "Portable AppImage",
        url: linuxAppImage,
        available: true,
        installerType: "AppImage",
      },
    ],
  },
};

export function isDesktopOs(value: ClientOs): value is DesktopOs {
  return value === "windows" || value === "macos" || value === "linux";
}

function classifyLabel(raw: string): ClientOs | null {
  const value = raw.trim().toLowerCase();
  if (!value) return null;
  if (value.includes("android")) return "android";
  if (value.includes("iphone") || value.includes("ipad") || value.includes("ipod") || value === "ios") return "ios";
  if (value.includes("cros") || value.includes("chrome os") || value.includes("chromeos")) return "unknown";
  if (value.includes("win")) return "windows";
  if (value.includes("mac")) return "macos";
  if (value.includes("linux")) return "linux";
  return null;
}

/** Local-only OS classification. Nothing here is sent to a server. */
export function detectOs(signals: OsSignals): ClientOs {
  const hinted = signals.userAgentDataPlatform?.trim();
  if (hinted) {
    const fromHint = classifyLabel(hinted);
    if (fromHint) return fromHint;
  }

  const haystack = `${signals.platform ?? ""} ${signals.userAgent ?? ""}`.toLowerCase();
  if (!haystack.trim()) return "unknown";
  if (haystack.includes("android")) return "android";
  if (/iphone|ipad|ipod/.test(haystack)) return "ios";
  if (haystack.includes("mac") && haystack.includes("mobile")) return "ios";
  if (haystack.includes("cros") || haystack.includes("chrome os")) return "unknown";
  if (haystack.includes("win")) return "windows";
  if (haystack.includes("mac")) return "macos";
  if (haystack.includes("linux")) return "linux";
  return "unknown";
}

type NavigatorWithHints = Navigator & {
  userAgentData?: { platform?: string };
};

export function readClientOs(): ClientOs {
  if (typeof navigator === "undefined") return "unknown";
  const hints = navigator as NavigatorWithHints;
  return detectOs({
    userAgentDataPlatform: hints.userAgentData?.platform,
    platform: navigator.platform,
    userAgent: navigator.userAgent,
  });
}

function trustedHttps(url: string): string | null {
  const trimmed = url.trim();
  if (!trimmed || /\s/.test(trimmed)) return null;
  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    return null;
  }
  if (parsed.protocol !== "https:") return null;
  if (parsed.username || parsed.password) return null;
  if (parsed.href !== trimmed) return null;
  return trimmed;
}

/**
 * Direct installer for Windows and macOS.
 * Linux has more than one package, so this stays empty and the chooser is used.
 */
export function configuredDownloadUrl(id: DesktopOs): string | null {
  if (id === "linux") return null;
  const release = downloads[id];
  if (!release?.available) return null;
  return trustedHttps(release.url);
}

/** Homepage and platform links for Linux open the package chooser. */
export function platformDownloadHref(id: DesktopOs): string | null {
  if (id === "linux") return downloadState(id) === "available" ? linuxPackageChooserHref : null;
  return configuredDownloadUrl(id);
}

export type DownloadState = "available" | "coming-soon";

/** One availability decision for the hero, the platform list, and the download section. */
export function downloadState(id: DesktopOs): DownloadState {
  if (id === "linux") return readyBuilds(id).length > 0 ? "available" : "coming-soon";
  return configuredDownloadUrl(id) ? "available" : "coming-soon";
}

/** Names a real download only when a trusted installer URL is configured. */
export function releaseActionLabel(id: DesktopOs): string {
  const label = downloads[id].label;
  if (downloadState(id) === "available") return `Download for ${label}`;
  return `${label} — Coming Soon`;
}

export function readyBuilds(id: DesktopOs): ReleaseBuild[] {
  return downloads[id].builds.filter((build) => build.available && trustedHttps(build.url));
}

export function otherPlatforms(current: ClientOs): DesktopOs[] {
  if (!isDesktopOs(current)) return [...desktopPlatforms];
  return desktopPlatforms.filter((id) => id !== current);
}
