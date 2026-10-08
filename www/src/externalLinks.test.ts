import { describe, expect, it } from "vitest";
import { articleResourceUrl, ecosystemLinks, externalLinks, officialSameAs, publicExternalUrl } from "./externalLinks";

describe("external destinations", () => {
  it("publishes only the verified GitHub repository", () => {
    expect(externalLinks.github.url).toBe("https://github.com/bradjohnson79/adeptui");
    expect(publicExternalUrl("github")).toBe("https://github.com/bradjohnson79/adeptui");
    expect(externalLinks.huggingFace.enabled).toBe(false);
    expect(externalLinks.huggingFace.url).toBe("");
    expect(publicExternalUrl("huggingFace")).toBeNull();
    expect(officialSameAs()).toEqual(["https://github.com/bradjohnson79/adeptui"]);
    expect(publicExternalUrl("comfyui")).toBe("https://www.comfy.org/");
    expect(officialSameAs()).not.toContain("https://www.comfy.org/");
    expect(JSON.stringify(externalLinks)).not.toContain("huggingface.co");
  });

  it("hides Hugging Face from the footer until a URL is enabled", () => {
    const labels = ecosystemLinks().map((item) => item.label);
    expect(labels).toEqual(["Documentation", "GitHub", "Contact", "Donate", "Downloads"]);
    expect(ecosystemLinks().find((item) => item.label === "Donate")?.href).toBe("https://ko-fi.com/G1G728D4FV");
    expect(ecosystemLinks().find((item) => item.label === "Contact")?.href).toBe("/contact");
    expect(ecosystemLinks().find((item) => item.label === "GitHub")?.href).toBe("https://github.com/bradjohnson79/adeptui");
    expect(ecosystemLinks().some((item) => item.href.includes("huggingface.co"))).toBe(false);
    expect(ecosystemLinks().some((item) => item.href.includes("comfy.org"))).toBe(false);
  });

  it("resolves article badges only for an enabled destination", () => {
    expect(articleResourceUrl("github", "repo")).toBe("https://github.com/bradjohnson79/adeptui");
    expect(articleResourceUrl("github", "/issues")).toBe("https://github.com/bradjohnson79/adeptui/issues");
    expect(articleResourceUrl("github", "https://github.com/example/other")).toBeNull();
    expect(articleResourceUrl("huggingFace", "repo")).toBeNull();
  });
});
