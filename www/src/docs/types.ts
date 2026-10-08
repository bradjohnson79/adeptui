export type DocStatus = "published" | "draft" | "needs-review";
export type Difficulty = "start" | "practice" | "technical";

export type DocFrontmatter = {
  title: string;
  summary: string;
  category: string;
  slug: string;
  tags: string[];
  difficulty: Difficulty;
  updated: string;
  status: DocStatus;
  seoTitle: string;
  seoDescription: string;
  related: string[];
  github: string;
  huggingFace: string;
};

export type DocBlock =
  | { type: "p"; html: string }
  | { type: "h"; level: 2 | 3; text: string; id: string }
  | { type: "list"; ordered: boolean; items: string[] }
  | { type: "pre"; code: string }
  | { type: "quote"; kind: "note" | "tip" | "warning" | "plain"; html: string }
  | { type: "table"; headers: string[]; rows: string[][] }
  | { type: "img"; alt: string; src: string };

export type DocCategory = {
  id: string;
  title: string;
  summary: string;
  group: "start" | "create" | "finish" | "systems" | "help";
};

export type DocArticle = DocFrontmatter & {
  href: string;
  blocks: DocBlock[];
  headings: { level: 2 | 3; text: string; id: string }[];
  plain: string;
  minutes: number;
};

export type SearchHit = {
  article: DocArticle;
  snippet: string;
};
