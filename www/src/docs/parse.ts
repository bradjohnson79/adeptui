import type { Difficulty, DocBlock, DocFrontmatter, DocStatus } from "./types";

const difficulties: Difficulty[] = ["start", "practice", "technical"];
const statuses: DocStatus[] = ["published", "draft", "needs-review"];

export function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function headingId(text: string): string {
  const id = text
    .toLowerCase()
    .replaceAll(/[^a-z0-9]+/g, "-")
    .replaceAll(/^-|-$/g, "");
  return id || "section";
}

function parseValue(raw: string): string | string[] {
  const value = raw.trim();
  if (value.startsWith("[") && value.endsWith("]")) {
    const inner = value.slice(1, -1).trim();
    if (!inner) return [];
    return inner.split(",").map((item) => item.trim().replaceAll(/^"|"$/g, ""));
  }
  return value.replaceAll(/^"|"$/g, "");
}

export function parseFrontmatter(source: string): { data: DocFrontmatter; body: string } {
  const match = source.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  if (!match?.[1]) throw new Error("Article is missing frontmatter.");
  const bag: Record<string, string | string[]> = {};
  for (const line of match[1].split(/\r?\n/)) {
    if (!line.trim()) continue;
    const split = line.indexOf(":");
    if (split < 1) throw new Error(`Bad frontmatter line: ${line}`);
    bag[line.slice(0, split).trim()] = parseValue(line.slice(split + 1));
  }
  const text = (key: string) => {
    const value = bag[key];
    if (typeof value !== "string" || !value.trim()) throw new Error(`Missing ${key}.`);
    return value.trim();
  };
  const list = (key: string) => {
    const value = bag[key];
    if (value === undefined) return [];
    if (Array.isArray(value)) return value.filter(Boolean);
    return [value];
  };
  const difficulty = (bag.difficulty as string | undefined) ?? "start";
  const status = text("status");
  if (!difficulties.includes(difficulty as Difficulty)) throw new Error(`Bad difficulty: ${difficulty}`);
  if (!statuses.includes(status as DocStatus)) throw new Error(`Bad status: ${status}`);
  return {
    data: {
      title: text("title"),
      summary: text("summary"),
      category: text("category"),
      slug: text("slug"),
      tags: list("tags"),
      difficulty: difficulty as Difficulty,
      updated: typeof bag.updated === "string" ? bag.updated : "",
      status: status as DocStatus,
      seoTitle: text("seoTitle"),
      seoDescription: text("seoDescription"),
      related: list("related"),
      github: typeof bag.github === "string" ? bag.github : "",
      huggingFace: typeof bag.huggingFace === "string" ? bag.huggingFace : "",
    },
    body: source.slice(match[0].length),
  };
}

function inline(text: string): string {
  let html = escapeHtml(text.trim());
  html = html.replaceAll(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replaceAll(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replaceAll(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_full, label: string, href: string) => {
    const allowed = href.startsWith("/") || href.startsWith("#") || href.startsWith("https://");
    return `<a href="${allowed ? href : "#"}">${label}</a>`;
  });
  return html;
}

function quoteKind(text: string): DocBlock & { type: "quote" } {
  const trimmed = text.trim();
  const kind = trimmed.startsWith("Warning:")
    ? "warning"
    : trimmed.startsWith("Tip:")
      ? "tip"
      : trimmed.startsWith("Note:")
        ? "note"
        : "plain";
  return { type: "quote", kind, html: inline(trimmed) };
}

export function parseMarkdown(body: string): DocBlock[] {
  const lines = body.replaceAll("\r\n", "\n").split("\n");
  const blocks: DocBlock[] = [];
  let index = 0;

  const pushParagraph = (chunk: string[]) => {
    const text = chunk.join(" ").trim();
    if (text) blocks.push({ type: "p", html: inline(text) });
  };

  while (index < lines.length) {
    const line = lines[index] ?? "";
    if (!line.trim()) {
      index += 1;
      continue;
    }
    if (line.startsWith("```")) {
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index]?.startsWith("```")) {
        code.push(lines[index] ?? "");
        index += 1;
      }
      index += 1;
      blocks.push({ type: "pre", code: code.join("\n") });
      continue;
    }
    const image = /^!\[([^\]]*)\]\(([^)\s]+)\)$/.exec(line.trim());
    if (image?.[2]?.startsWith("/product/") || image?.[2]?.startsWith("/brand/") || image?.[2]?.startsWith("/film/")) {
      blocks.push({ type: "img", alt: image[1] ?? "", src: image[2] });
      index += 1;
      continue;
    }
    if (line.startsWith("## ")) {
      const text = line.slice(3).trim();
      blocks.push({ type: "h", level: 2, text, id: headingId(text) });
      index += 1;
      continue;
    }
    if (line.startsWith("### ")) {
      const text = line.slice(4).trim();
      blocks.push({ type: "h", level: 3, text, id: headingId(text) });
      index += 1;
      continue;
    }
    if (line.startsWith("> ")) {
      const quote: string[] = [];
      while (index < lines.length && lines[index]?.startsWith("> ")) {
        quote.push((lines[index] ?? "").slice(2));
        index += 1;
      }
      blocks.push(quoteKind(quote.join(" ")));
      continue;
    }
    if (line.startsWith("|")) {
      const rows: string[][] = [];
      while (index < lines.length && lines[index]?.startsWith("|")) {
        const cells = (lines[index] ?? "")
          .split("|")
          .slice(1, -1)
          .map((cell) => cell.trim());
        if (!cells.every((cell) => /^:?-+:?$/.test(cell))) rows.push(cells);
        index += 1;
      }
      const headers = rows.shift() ?? [];
      blocks.push({ type: "table", headers, rows });
      continue;
    }
    if (/^[-*] /.test(line) || /^\d+\. /.test(line)) {
      const ordered = /^\d+\. /.test(line);
      const items: string[] = [];
      while (index < lines.length && (ordered ? /^\d+\. /.test(lines[index] ?? "") : /^[-*] /.test(lines[index] ?? ""))) {
        items.push(inline((lines[index] ?? "").replace(ordered ? /^\d+\. / : /^[-*] /, "")));
        index += 1;
      }
      blocks.push({ type: "list", ordered, items });
      continue;
    }
    const chunk = [line];
    index += 1;
    while (index < lines.length && lines[index]?.trim() && !/^(#|>|\||```|[-*] |\d+\. )/.test(lines[index] ?? "")) {
      chunk.push(lines[index] ?? "");
      index += 1;
    }
    pushParagraph(chunk);
  }
  return blocks;
}

export function plainTextFrom(body: string): string {
  return body
    .replaceAll(/```[\s\S]*?```/g, " ")
    .replaceAll(/[#>*`|[\]]/g, " ")
    .replaceAll(/\s+/g, " ")
    .trim();
}
