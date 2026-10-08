import { readFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";
import { openTrustedStatusLink, productStatus } from "./productStatus";

describe("home product status", () => {
  it("points the beta notice at the public bug-report form", () => {
    const url = new URL(productStatus.bugReportUrl);
    expect(url.origin).toBe("https://adeptui.org");
    expect(url.pathname).toBe("/contact");
    expect(url.searchParams.get("category")).toBe("bug");
    expect(productStatus.status).toBe("beta");
    expect(productStatus.linkLabel).toBe("Report any bugs here");
  });

  it("opens only the fixed address through the desktop bridge", () => {
    const openExternal = vi.fn(async () => ({ ok: true }));
    const preventDefault = vi.fn();
    openTrustedStatusLink({ preventDefault }, { openExternal });
    expect(preventDefault).toHaveBeenCalledOnce();
    expect(openExternal).toHaveBeenCalledWith("https://adeptui.org/contact?category=bug");
  });

  it("leaves a normal browser link alone when the desktop bridge is absent", () => {
    const preventDefault = vi.fn();
    openTrustedStatusLink({ preventDefault }, undefined);
    expect(preventDefault).not.toHaveBeenCalled();
  });

  it("is mounted once on Home, under the header and above the hero", () => {
    const home = readFileSync(new URL("../pages/Home.tsx", import.meta.url), "utf8");
    const notice = home.indexOf("<BetaNotice />");
    const chrome = home.indexOf("<StudioChrome");
    const hero = home.indexOf("<GenerationStudioHero />");
    expect(home.match(/<BetaNotice \/>/g)).toHaveLength(1);
    expect(notice).toBeGreaterThan(chrome);
    expect(notice).toBeLessThan(hero);
    expect(readFileSync(new URL("./BetaNotice.tsx", import.meta.url), "utf8")).not.toContain("localhost");
  });
});
