import { describe, expect, it } from "vitest";
import { docCategories } from "./categories";
import { articlesIn, hiddenArticles, publishedArticles, searchDocs } from "./catalog";
import { parseFrontmatter, parseMarkdown } from "./parse";

const sample = `---
title: Sample
summary: A sample article about storyboard panels.
category: storyboard
slug: sample
tags: [storyboard, planning]
difficulty: start
updated: 2026-10-06
status: published
seoTitle: Sample storyboard article
seoDescription: Explains storyboard panels before video generation.
related: []
---

## What this does

Storyboard panels come **before** the render.

- Plan the shot
- Then generate

> Tip: Look at the board first.
`;

describe("docs parser", () => {
  it("reads frontmatter and markdown blocks", () => {
    const parsed = parseFrontmatter(sample);
    expect(parsed.data.slug).toBe("sample");
    expect(parsed.data.tags).toEqual(["storyboard", "planning"]);
    const blocks = parseMarkdown(parsed.body);
    expect(blocks.some((block) => block.type === "h" && block.text === "What this does")).toBe(true);
    expect(blocks.some((block) => block.type === "list")).toBe(true);
    expect(blocks.some((block) => block.type === "quote" && block.kind === "tip")).toBe(true);
  });
});

describe("docs catalog", () => {
  it("publishes every category and hides unpublished articles", () => {
    for (const category of docCategories) {
      expect(articlesIn(category.id).length).toBeGreaterThan(0);
    }
    expect(hiddenArticles.some((article) => article.status === "needs-review")).toBe(true);
    expect(publishedArticles.some((article) => article.status !== "published")).toBe(false);
    expect(publishedArticles.some((article) => article.slug === "update-channels")).toBe(false);
  });

  it("includes the foundational guides", () => {
    const slugs = new Set(publishedArticles.map((article) => article.slug));
    for (const slug of [
      "what-is-adept-ui",
      "installing-adept-ui",
      "your-first-project",
      "understanding-the-workflow",
      "what-is-co-director",
      "creating-a-character",
      "using-storyboard-studio",
      "ai-video-generation",
      "what-is-timeline",
      "shot-continuation",
      "what-is-magi",
      "local-vs-api-models",
      "running-ai-models-locally",
      "troubleshooting-generation",
      "ai-film-from-scratch",
    ]) {
      expect(slugs.has(slug)).toBe(true);
    }
  });

  it("keeps public docs free of hype and exact-match claims", () => {
    const banned = ["revolutionary", "game-changing", "best-in-class", "unmatched", "industry-leading", "frame-perfect"];
    for (const article of [...publishedArticles, ...hiddenArticles]) {
      const blob = `${article.title}\n${article.summary}\n${article.seoDescription}\n${article.plain}`.toLowerCase();
      for (const phrase of banned) {
        expect(blob.includes(phrase), `${article.slug} contains ${phrase}`).toBe(false);
      }
    }
  });

  it("finds storyboard guidance from the search index", () => {
    const hits = searchDocs(publishedArticles, "storyboard panels");
    expect(hits.length).toBeGreaterThan(0);
    expect(hits[0]?.article.summary.length).toBeGreaterThan(40);
    expect(hits[0]?.snippet.length).toBeGreaterThan(10);
    expect(hits.some((hit) => hit.article.slug === "update-channels")).toBe(false);
  });

  it("shows a GitHub badge only on the article that names the repository", () => {
    const contributing = publishedArticles.find((article) => article.slug === "contributing");
    expect(contributing?.github).toBe("repo");
    expect(publishedArticles.filter((article) => article.github).map((article) => article.slug)).toEqual(["contributing"]);
    expect(publishedArticles.some((article) => article.huggingFace)).toBe(false);
  });

  it("resolves related guides to published articles", () => {
    const slugs = new Set(publishedArticles.map((article) => article.slug));
    expect(slugs.size).toBe(publishedArticles.length);
    for (const article of publishedArticles) {
      for (const related of article.related) {
        expect(slugs.has(related), `${article.slug} -> ${related}`).toBe(true);
      }
    }
  });
});
