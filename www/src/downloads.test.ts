import { describe, expect, it } from "vitest";
import {
  configuredDownloadUrl,
  detectOs,
  downloadState,
  downloads,
  linuxPackageChooserHref,
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
  it("publishes the 1.1.1 desktop installers", () => {
    expect(downloads.windows.available).toBe(true);
    expect(downloads.macos.available).toBe(true);
    expect(downloads.linux.available).toBe(true);
    expect(configuredDownloadUrl("windows")).toMatch(/Adept\.UI-Setup-1\.1\.1-win-x64\.exe$/);
    expect(configuredDownloadUrl("macos")).toMatch(/Adept\.UI-1\.1\.1-mac-arm64\.dmg$/);
    expect(configuredDownloadUrl("linux")).toBeNull();
    expect(platformDownloadHref("linux")).toBe(linuxPackageChooserHref);
    expect(platformDownloadHref("windows")).toMatch(/Adept\.UI-Setup-1\.1\.1-win-x64\.exe$/);
    expect(platformDownloadHref("macos")).toMatch(/Adept\.UI-1\.1\.1-mac-arm64\.dmg$/);
    expect(readyBuilds("linux").map((build) => build.installerType)).toEqual(["deb", "rpm", "AppImage"]);
    expect(readyBuilds("linux").map((build) => build.audience)).toEqual([
      "Ubuntu / Debian",
      "Fedora / RHEL",
      "Universal Linux",
    ]);
    expect(readyBuilds("linux").find((build) => build.installerType === "AppImage")?.url).toMatch(/\.AppImage$/);
    expect(readyBuilds("linux").find((build) => build.installerType === "deb")?.url).toMatch(/\.deb$/);
    expect(readyBuilds("linux").find((build) => build.installerType === "rpm")?.url).toMatch(/\.rpm$/);
    for (const release of Object.values(downloads)) {
      expect(release.version).toBe("1.1.1");
      expect(downloadState(release.id)).toBe("available");
      expect(releaseActionLabel(release.id)).toBe(`Download for ${release.label}`);
      if (release.id === "linux") {
        expect(platformDownloadHref(release.id)).toBe(linuxPackageChooserHref);
      } else {
        expect(configuredDownloadUrl(release.id)?.startsWith("https://github.com/bradjohnson79/adeptui/releases/download/v1.1.1/")).toBe(true);
      }
    }
  });

  it("rejects a URL that is not a configured https release", () => {
    expect(downloads.windows.url.includes("?")).toBe(false);
    expect(downloads.windows.url.startsWith("https://")).toBe(true);
  });
});
