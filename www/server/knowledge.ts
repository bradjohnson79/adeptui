import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { faq, site } from "../src/content";
import { categoryById } from "../src/docs/categories";
import { parseFrontmatter, parseMarkdown } from "../src/docs/parse";
import { externalLinks } from "../src/externalLinks";
import type { KnowledgeChunk, SourceType, StoredChunk } from "./types";
import { embedText } from "./vectors";

function plainBlock(html: string): string {
  return html
    .replaceAll(/<[^>]+>/g, " ")
    .replaceAll("&amp;", "&")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", '"')
    .replaceAll(/\s+/g, " ")
    .trim();
}

function chunk(partial: Omit<KnowledgeChunk, "id">): KnowledgeChunk {
  return {
    ...partial,
    id: `${partial.sourceType}:${partial.slug}:${partial.heading}`.toLowerCase().replaceAll(/[^a-z0-9:_-]+/g, "-"),
  };
}

function fromArticle(source: string, category: string, fileSlug: string): KnowledgeChunk[] {
  const { data, body } = parseFrontmatter(source);
  if (data.status !== "published" || data.slug !== fileSlug || data.category !== category) return [];
  const blocks = parseMarkdown(body);
  const chunks: KnowledgeChunk[] = [];
  let heading = "Overview";
  let buffer: string[] = [data.summary];
  const push = () => {
    const text = buffer.join(" ").replaceAll(/\s+/g, " ").trim();
    buffer = [];
    if (text.length < 40) return;
    chunks.push(
      chunk({
        title: data.title,
        category: categoryById.get(data.category)?.title ?? data.category,
        article: data.title,
        slug: data.slug,
        heading,
        url: `/docs/${data.category}/${data.slug}`,
        tags: data.tags,
        updated: data.updated,
        sourceType: "docs",
        text,
      }),
    );
  };
  for (const block of blocks) {
    if (block.type === "h" && block.level === 2) {
      push();
      heading = block.text;
      continue;
    }
    if (block.type === "p" || block.type === "quote") buffer.push(plainBlock(block.html));
    if (block.type === "list") buffer.push(block.items.map((item) => plainBlock(item)).join(" "));
    if (block.type === "pre") buffer.push(block.code);
  }
  push();
  return chunks;
}

function publicChunks(): KnowledgeChunk[] {
  const github = externalLinks.github.enabled ? externalLinks.github.url : "";
  const facts: Omit<KnowledgeChunk, "id">[] = [
    {
      title: site.title,
      category: "Website",
      article: "About Adept UI",
      slug: "about",
      heading: "Overview",
      url: "/",
      tags: ["adept ui", "filmmaking"],
      updated: "",
      sourceType: "website",
      text: site.description,
    },
    {
      title: "Platforms and download",
      category: "Installation",
      article: "Download",
      slug: "download",
      heading: "Installers",
      url: "/#download",
      tags: ["download", "windows", "macos", "linux"],
      updated: "",
      sourceType: "release",
      text: "Adept UI 1.1 is free desktop software for Windows, macOS, and Linux, built around an open AI ecosystem. The website download provides the Windows setup, the macOS disk image, and a Linux package chooser. Ubuntu and Debian-based systems use the .deb package. Fedora and compatible RPM-based systems use the .rpm package. A portable AppImage is also available. This website does not publish hardware minimums such as RAM, VRAM, or disk size. The local application is free. Third-party APIs may cost money, and a future Adept Cloud may have its own charges. A phone is not the production app.",
    },
    {
      title: "Supported models",
      category: "Models",
      article: "Model map",
      slug: "models",
      heading: "Current models",
      url: "/docs/models/local-vs-api-models",
      tags: ["models", "minimax", "ltx", "seedance"],
      updated: "",
      sourceType: "models",
      text: "Local video, when installed, is MiniMax H3, LTX 2.5, and Hunyuan 1.5 Distilled. Hosted video through fal.ai is Seedance 2.0, Seedance 2.5, Kling 2.5 Turbo Pro, Kling 3.0, Veo 3.1, Runway Gen-3 Turbo, Flux 3.0, Happy Horse 1.0, and Google Gemini Omni. Local stills, when installed, include Illustrious XL, Qwen-Image, Z-Image, and Flux. WAN is not a current Adept UI video model. The model you select is the one that runs. Adept UI does not publish a VRAM number or a price for these models.",
    },
    {
      title: "GitHub",
      category: "Developer",
      article: "Repository",
      slug: "github",
      heading: "Source repository",
      url: github || "/docs/developer/contributing",
      tags: ["github", "source"],
      updated: "",
      sourceType: "github",
      text: `The public Adept UI repository is ${github}. It is for source code, issues, and development. It is not the installer, and no GitHub release is published. Adept UI is free AI filmmaking software built around an open AI ecosystem. It is not open-source software. A public repository is not permission to fork, rebrand, or redistribute Adept UI. Creators learn the product in the documentation, not from a README.`,
    },
    {
      title: "Hugging Face",
      category: "Models",
      article: "Hugging Face",
      slug: "hugging-face",
      heading: "Not available",
      url: "/docs/local-ai/installing-models",
      tags: ["hugging face", "models"],
      updated: "",
      sourceType: "huggingface",
      text: "Adept UI does not yet have an official Hugging Face destination. Do not send visitors to another organization's page that happens to use a similar name. Supported local models are installed in Adept Setup. The website link stays hidden until an official Adept UI URL exists.",
    },
  ];
  const faqChunks = faq.items.map((item) =>
    chunk({
      title: item.q,
      category: "Questions",
      article: item.q,
      slug: item.q.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-").replaceAll(/^-|-$/g, ""),
      heading: "Answer",
      url: "/#faq",
      tags: ["faq"],
      updated: "",
      sourceType: "faq" as SourceType,
      text: `${item.q} ${item.a}`,
    }),
  );
  return [...facts.map((item) => chunk(item)), ...faqChunks];
}

export function readPublishedDocs(docsRoot: string): KnowledgeChunk[] {
  const chunks: KnowledgeChunk[] = [];
  for (const category of readdirSync(docsRoot, { withFileTypes: true })) {
    if (!category.isDirectory()) continue;
    const dir = path.join(docsRoot, category.name);
    for (const file of readdirSync(dir)) {
      if (!file.endsWith(".md")) continue;
      const source = readFileSync(path.join(dir, file), "utf8");
      chunks.push(...fromArticle(source, category.name, file.replace(/\.md$/, "")));
    }
  }
  return chunks;
}

export function buildKnowledge(docsRoot: string): StoredChunk[] {
  const chunks = [...readPublishedDocs(docsRoot), ...publicChunks()];
  return chunks.map((item) => ({ ...item, vector: embedText(`${item.title} ${item.heading} ${item.text}`) }));
}
