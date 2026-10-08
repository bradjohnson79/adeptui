import { categoryById } from "./categories";
import { parseFrontmatter, parseMarkdown, plainTextFrom } from "./parse";
import type { DocArticle, SearchHit } from "./types";

export function articleFromSource(source: string, fileSlug: string): DocArticle {
  const { data, body } = parseFrontmatter(source);
  if (data.slug !== fileSlug) throw new Error(`${fileSlug} frontmatter slug is ${data.slug}.`);
  if (!categoryById.has(data.category)) throw new Error(`Unknown category ${data.category}.`);
  const blocks = parseMarkdown(body);
  const headings = blocks.flatMap((block) => (block.type === "h" ? [{ level: block.level, text: block.text, id: block.id }] : []));
  const plain = plainTextFrom(body);
  const words = plain.split(/\s+/).filter(Boolean).length;
  return {
    ...data,
    href: `/docs/${data.category}/${data.slug}`,
    blocks,
    headings,
    plain,
    minutes: Math.max(1, Math.round(words / 220)),
  };
}

export function buildCatalog(entries: { fileSlug: string; category: string; source: string }[]): {
  published: DocArticle[];
  hidden: DocArticle[];
} {
  const published: DocArticle[] = [];
  const hidden: DocArticle[] = [];
  for (const entry of entries) {
    const article = articleFromSource(entry.source, entry.fileSlug);
    if (article.category !== entry.category) {
      throw new Error(`${entry.fileSlug} is filed under ${entry.category} but declares ${article.category}.`);
    }
    if (article.status === "published") published.push(article);
    else hidden.push(article);
  }
  published.sort((a, b) => a.title.localeCompare(b.title));
  return { published, hidden };
}

export function searchDocs(articles: DocArticle[], query: string): SearchHit[] {
  const terms = query.toLowerCase().split(/\s+/).filter((term) => term.length > 1);
  if (!terms.length) return [];
  const scored = articles.flatMap((article) => {
    const title = article.title.toLowerCase();
    const summary = article.summary.toLowerCase();
    const tags = article.tags.join(" ").toLowerCase();
    const headings = article.headings.map((heading) => heading.text.toLowerCase()).join(" ");
    const body = article.plain.toLowerCase();
    let score = 0;
    for (const term of terms) {
      if (title.includes(term)) score += 8;
      if (summary.includes(term)) score += 5;
      if (tags.includes(term)) score += 4;
      if (headings.includes(term)) score += 3;
      if (body.includes(term)) score += 1;
    }
    if (score === 0) return [];
    return [{ article, score, snippet: snippetFor(article, terms[0] ?? "") }];
  });
  scored.sort((a, b) => b.score - a.score || a.article.title.localeCompare(b.article.title));
  return scored.map(({ article, snippet }) => ({ article, snippet }));
}

function snippetFor(article: DocArticle, term: string): string {
  const source = article.plain;
  const at = source.toLowerCase().indexOf(term.toLowerCase());
  if (at < 0) return article.summary;
  const start = Math.max(0, at - 60);
  const end = Math.min(source.length, at + term.length + 90);
  const slice = source.slice(start, end).trim();
  return `${start > 0 ? "…" : ""}${slice}${end < source.length ? "…" : ""}`;
}

const rawDocs = import.meta.glob("../../docs/**/*.md", {
  eager: true,
  query: "?raw",
  import: "default",
}) as Record<string, string>;

function entriesFromGlob() {
  return Object.entries(rawDocs).map(([path, source]) => {
    const parts = path.split("/");
    const file = parts.at(-1) ?? "";
    const category = parts.at(-2) ?? "";
    return { fileSlug: file.replace(/\.md$/, ""), category, source };
  });
}

const catalog = buildCatalog(entriesFromGlob());

export const publishedArticles = catalog.published;
export const hiddenArticles = catalog.hidden;

export function articlesIn(categoryId: string): DocArticle[] {
  return publishedArticles.filter((article) => article.category === categoryId);
}

export function findArticle(categoryId: string, slug: string): DocArticle | undefined {
  return publishedArticles.find((article) => article.category === categoryId && article.slug === slug);
}

export function findHidden(categoryId: string, slug: string): DocArticle | undefined {
  return hiddenArticles.find((article) => article.category === categoryId && article.slug === slug);
}

export function relatedArticles(article: DocArticle): DocArticle[] {
  return article.related
    .map((slug) => publishedArticles.find((item) => item.slug === slug))
    .filter((item): item is DocArticle => Boolean(item));
}
