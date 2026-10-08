export const CHAT_MODEL = "gpt-5-mini" as const;
export const EMBEDDING_MODEL = "text-embedding-3-small" as const;

export type SourceType = "docs" | "website" | "faq" | "release" | "models" | "github" | "huggingface";

export type KnowledgeChunk = {
  id: string;
  title: string;
  category: string;
  article: string;
  slug: string;
  heading: string;
  url: string;
  tags: string[];
  updated: string;
  sourceType: SourceType;
  text: string;
};

export type StoredChunk = KnowledgeChunk & {
  vector: number[];
};

export type GuidePage = {
  url: string;
  title: string;
  category: string;
  slug: string;
};

export type GuideTurn = {
  role: "user" | "assistant";
  content: string;
};

export type GuideSource = {
  title: string;
  heading: string;
  url: string;
  category: string;
};

export type ScoredChunk = {
  chunk: StoredChunk;
  score: number;
  lexical: number;
  semantic: number;
};
