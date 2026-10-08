import path from "node:path";
import { describe, expect, it } from "vitest";
import { buildKnowledge } from "./knowledge";
import { citationSources, retrieve } from "./retrieve";

const chunks = buildKnowledge(path.join(process.cwd(), "docs"));

function titles(question: string, page?: { url: string; title: string; category: string; slug: string }) {
  return retrieve(question, chunks, page).map((hit) => hit.chunk.slug);
}

describe("website knowledge retrieval", () => {
  it("does not index unpublished notes", () => {
    expect(chunks.some((chunk) => chunk.slug === "update-channels" || chunk.text.toLowerCase().includes("needs owner verification"))).toBe(false);
  });

  it("finds the foundational guides", () => {
    expect(titles("What is Adept UI?")).toContain("what-is-adept-ui");
    expect(titles("How do I install Adept UI?")).toContain("installing-adept-ui");
    expect(titles("Does it work on Linux?").some((slug) => ["system-requirements", "installing-adept-ui", "download"].includes(slug))).toBe(true);
    expect(titles("What is Co-Director?")).toContain("what-is-co-director");
    expect(titles("How does Timeline continuation work?")).toContain("shot-continuation");
    expect(titles("What is MAGI?")).toContain("what-is-magi");
    expect(titles("Can I run AI video locally?")).toContain("running-ai-models-locally");
    expect(titles("Which video models are supported?")).toContain("models");
    expect(titles("Where are models stored?")).toContain("installing-models");
    const failed = titles("My generation failed. What should I check?");
    expect(failed.join("|")).toContain("troubleshooting-generation");
    expect(titles("Where is the GitHub?")).toContain("github");
    expect(titles("Where is the Hugging Face?")).toContain("hugging-face");
  });

  it("uses lexical matching for an undefined error code and does not invent a hit", () => {
    const hits = retrieve("What does H3_RESOLUTION_UNSUPPORTED mean?", chunks);
    expect(chunks.some((chunk) => chunk.text.includes("H3_RESOLUTION_UNSUPPORTED"))).toBe(false);
    expect(hits).toEqual([]);
  });

  it("connects everyday wording about video size to resolution guidance", () => {
    const hits = titles("Why won't my video size work?");
    expect(hits.some((slug) => ["aspect-ratios", "ai-video-generation", "choosing-a-video-model"].includes(slug))).toBe(true);
  });

  it("prefers the article the visitor is reading", () => {
    const hits = retrieve("Why would I use this?", chunks, {
      url: "/docs/timeline/shot-continuation",
      title: "Shot Continuation",
      category: "timeline",
      slug: "shot-continuation",
    });
    expect(hits[0]?.chunk.slug).toBe("shot-continuation");
    expect(citationSources(hits).length).toBeLessThanOrEqual(3);
  });
});
