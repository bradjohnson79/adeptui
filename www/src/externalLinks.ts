/**
 * Official public destinations for Adept UI.
 * Hugging Face stays disabled until an Adept UI profile exists.
 * huggingface.co/adept is a different company and is not this product.
 */

import { kofi } from "./support";

export const externalLinks = {
  github: {
    label: "GitHub",
    url: "https://github.com/bradjohnson79/adeptui",
    enabled: true,
  },
  huggingFace: {
    label: "Hugging Face",
    url: "",
    enabled: false,
  },
  comfyui: {
    label: "ComfyUI",
    url: "https://www.comfy.org/",
    enabled: true,
  },
} as const;

export type ExternalKey = keyof typeof externalLinks;

export function publicExternalUrl(key: ExternalKey): string | null {
  const item = externalLinks[key];
  if (!item.enabled) return null;
  if (!item.url.startsWith("https://")) return null;
  return item.url;
}

/** Article frontmatter may name `repo` or a path on the official destination. It may not embed a URL. */
export function articleResourceUrl(key: ExternalKey, token: string | undefined): string | null {
  const base = publicExternalUrl(key);
  const value = token?.trim();
  if (!base || !value) return null;
  if (value === "repo") return base;
  if (value.startsWith("/") && !value.startsWith("//") && !value.includes("://")) return `${base}${value}`;
  return null;
}

export function officialSameAs(): string[] {
  return (["github", "huggingFace"] as const)
    .map((key) => publicExternalUrl(key))
    .filter((url): url is string => Boolean(url));
}

export function ecosystemLinks(): { href: string; label: string; external: boolean }[] {
  const items: { href: string; label: string; external: boolean }[] = [
    { href: "/docs", label: "Documentation", external: false },
  ];
  const github = publicExternalUrl("github");
  if (github) items.push({ href: github, label: externalLinks.github.label, external: true });
  const huggingFace = publicExternalUrl("huggingFace");
  if (huggingFace) items.push({ href: huggingFace, label: externalLinks.huggingFace.label, external: true });
  items.push({ href: "/contact", label: "Contact", external: false });
  items.push({ href: kofi.url, label: kofi.label, external: true });
  items.push({ href: "#download", label: "Downloads", external: false });
  return items;
}
