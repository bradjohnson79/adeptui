import { describe, expect, it } from "vitest";
import {
  audience,
  coDirector,
  cta,
  download,
  finale,
  faq,
  film,
  footer,
  hero,
  localApi,
  magi,
  models,
  nav,
  platform,
  sectionIds,
  shots,
  site,
  storyboard,
  systems,
  timeline,
  why,
  workflow,
  workspace,
} from "./content";

function collect(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(collect);
  if (value && typeof value === "object") return Object.values(value).flatMap(collect);
  return [];
}

const copy = collect({
  site,
  nav,
  cta,
  hero,
  download,
  shots,
  film,
  storyboard,
  why,
  workspace,
  coDirector,
  workflow,
  systems,
  models,
  timeline,
  magi,
  localApi,
  platform,
  finale,
  faq,
  footer,
  audience,
});

describe("public site claims", () => {
  it("keeps every navigation target on the page", () => {
    const ids = new Set<string>(sectionIds);
    for (const item of [...nav, ...footer.links]) {
      if (item.href.startsWith("/docs") || item.href === "/contact") continue;
      expect(item.href.startsWith("#")).toBe(true);
      expect(ids.has(item.href.slice(1))).toBe(true);
    }
    const labels = nav.map((item) => item.label);
    expect(labels.indexOf("Contact")).toBe(labels.indexOf("About") + 1);
    expect(nav.find((item) => item.label === "Contact")?.href).toBe("/contact");
    expect(ids.has(cta.href.slice(1))).toBe(true);
    expect(ids.has(hero.explore.href.slice(1))).toBe(true);
    expect(ids.has(finale.cta.href.slice(1))).toBe(true);
  });

  it("avoids hype and unsupported guarantees", () => {
    const blob = copy.join("\n").toLowerCase();
    for (const phrase of [
      "revolutionize",
      "unleash",
      "the future is here",
      "next-generation",
      "transform your workflow",
      "guarantees perfect continuity",
      "frame-perfect",
    ]) {
      expect(blob.includes(phrase)).toBe(false);
    }
    expect(blob).toContain("does not guarantee");
  });

  it("lists verified engines and qualifies SceneCraft", () => {
    expect(models.localVideo).toEqual(["MiniMax H3", "LTX 2.5", "Hunyuan 1.5 Distilled"]);
    expect(models.localVideo.indexOf("Hunyuan 1.5 Distilled")).toBe(models.localVideo.indexOf("LTX 2.5") + 1);
    expect(models.apiVideo).toContain("Seedance 2.0");
    expect(models.apiVideo).toContain("Kling 2.5 Turbo Pro");
    expect(models.apiVideo).toEqual(expect.arrayContaining(["Kling 3.0", "Flux 3.0", "Happy Horse 1.0", "Google Gemini Omni"]));
    expect(models.apiVideo).toContain("Veo 3.1");
    expect(models.apiVideo.join(" ")).not.toMatch(/\bWAN\b/);
    expect(localApi.comfy.heading).toBe("Built on ComfyUI Workflows");
    expect(localApi.comfy.body).toMatch(/ComfyUI/);
    expect(localApi.comfy.body).toMatch(/local AI generation/);
    expect(localApi.comfy.body).toMatch(/AI filmmaking workflow/);
    expect(localApi.comfy.body.toLowerCase()).not.toMatch(/wrapper|frontend|skin/);
    const worlds = systems.cards.find((card) => card.name === "Worlds and Props");
    expect(worlds?.note).toMatch(/later release/i);
  });

  it("does not invent price, date, or a download", () => {
    const blob = copy.join("\n").toLowerCase();
    expect(blob).not.toMatch(/\$\d/);
    expect(blob).not.toMatch(/\b20\d{2}\b/);
    expect(blob).not.toContain("download now");
    expect(blob).toContain("will be announced with the release");
    expect(blob).not.toMatch(/free and open-source/);
    expect(blob).not.toMatch(/free & open source/);
    expect(blob).not.toMatch(/free and open source/);
    expect(blob).not.toMatch(/is an open-source/);
    expect(blob).not.toMatch(/adept ui is open-source/);
    expect(blob).toContain("free ai filmmaking software");
    expect(blob).toContain("open ai ecosystem");
    expect(blob).toContain("not open-source software");
    expect(blob).not.toMatch(/\bstable release\b/);
    expect(blob).not.toMatch(/production-ready/);
    expect(blob).toContain("in beta");
    expect(blob).toContain("not a license for the adept ui application");
  });
});
