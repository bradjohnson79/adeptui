import { describe, expect, it } from "vitest";
import {
  configuredDownloadUrl,
  detectOs,
  downloadState,
  downloads,
  installCommand,
  platformDownloadHref,
  readyBuilds,
  releaseActionLabel,
} from "./downloads";

describe("operating system detection", () => {
  it("recommends Windows, macOS, and Linux from client hints", () => {
    expect(detectOs({ userAgentDataPlatform: "Windows" })).toBe("windows");
    expect(detectOs({ userAgentDataPlatform: "macOS" })).toBe("macos");
    expect(detectOs({ userAgentDataPlatform: "Linux" })).toBe("linux");
  });

  it("falls back to platform and user agent", () => {
    expect(
      detectOs({
        platform: "Win32",
        userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      }),
    ).toBe("windows");
    expect(
      detectOs({
        platform: "MacIntel",
        userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15",
      }),
    ).toBe("macos");
    expect(
      detectOs({
        platform: "Linux x86_64",
        userAgent: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
      }),
    ).toBe("linux");
    expect(
      detectOs({
        userAgentDataPlatform: "Linux",
        userAgent: "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
      }),
    ).toBe("linux");
    expect(
      detectOs({
        userAgent: "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
      }),
    ).toBe("linux");
    expect(
      detectOs({
        userAgent: "Mozilla/5.0 (X11; Debian; Linux x86_64) AppleWebKit/537.36",
      }),
    ).toBe("linux");
  });

  it("treats phones and tablets as desktop-only visitors", () => {
    expect(
      detectOs({
        userAgent:
          "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
      }),
    ).toBe("ios");
    expect(
      detectOs({
        platform: "MacIntel",
        userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
      }),
    ).toBe("ios");
    expect(
      detectOs({
        userAgentDataPlatform: "Android",
        userAgent: "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36",
      }),
    ).toBe("android");
  });

  it("does not guess an unknown desktop", () => {
    expect(detectOs({})).toBe("unknown");
    expect(detectOs({ userAgentDataPlatform: "Chrome OS" })).toBe("unknown");
    expect(detectOs({ platform: "", userAgent: "Mozilla/5.0" })).toBe("unknown");
  });
});

describe("download configuration", () => {
  it("publishes Windows, Linux, and macOS install commands", () => {
    expect(downloads.windows.available).toBe(true);
    expect(downloads.linux.available).toBe(true);
    expect(downloads.macos.available).toBe(true);
    expect(installCommand("windows")).toBe("irm https://adeptui.org/install.ps1 | iex");
    expect(installCommand("linux")).toBe("curl -fsSL https://adeptui.org/install.sh | bash");
    expect(installCommand("macos")).toBe("curl -fsSL https://adeptui.org/install.sh | bash");
    expect(platformDownloadHref("windows")).toBe("#download");
    expect(platformDownloadHref("linux")).toBe("#download");
    expect(platformDownloadHref("macos")).toBe("#download");
    expect(configuredDownloadUrl("macos")).toMatch(/Adept\.UI-1\.1\.5-terminal-r5-mac-arm64\.zip$/);
    expect(configuredDownloadUrl("windows")).toMatch(/Adept\.UI-1\.1\.5-terminal-r5-win-x64\.zip$/);
    expect(readyBuilds("linux").map((build) => build.installerType)).toEqual(["zip"]);
    expect(downloadState("windows")).toBe("available");
    expect(downloadState("linux")).toBe("available");
    expect(downloadState("macos")).toBe("available");
    expect(releaseActionLabel("windows")).toBe("Install Adept UI");
    expect(releaseActionLabel("linux")).toBe("Install Adept UI");
    expect(releaseActionLabel("macos")).toBe("Install Adept UI");
    expect(downloads.windows.version).toBe("1.1.5");
    expect(downloads.linux.version).toBe("1.1.5");
    expect(downloads.macos.version).toBe("1.1.5");
  });

  it("rejects a URL that is not a configured https release", () => {
    expect(downloads.windows.url.includes("?")).toBe(false);
    expect(downloads.windows.url.startsWith("https://")).toBe(true);
  });
});
