import { articleResourceUrl, externalLinks, publicExternalUrl } from "../externalLinks";

function GitHubMark() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" width="18" height="18">
      <path
        fill="currentColor"
        d="M8 0C3.58 0 0 3.58 0 8a8 8 0 0 0 5.47 7.59c.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.7 7.7 0 0 1 2-.27c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"
      />
    </svg>
  );
}

function HuggingFaceMark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" width="18" height="18">
      <path
        fill="currentColor"
        d="M12.1 2.2c-2.4.1-4.3 1.6-5.2 3.5-.3.6-.4 1.3-.3 2 .2.8.7 1.5 1.4 1.9-.6.5-1 1.2-1.1 2-.1.9.2 1.8.8 2.5-1 .7-1.6 1.8-1.6 3 0 2.1 1.8 3.8 4 3.8.7 0 1.4-.2 2-.5.6.3 1.3.5 2 .5 2.2 0 4-1.7 4-3.8 0-1.2-.6-2.3-1.6-3 .6-.7.9-1.6.8-2.5-.1-.8-.5-1.5-1.1-2 .7-.4 1.2-1.1 1.4-1.9.1-.7 0-1.4-.3-2C16.4 3.8 14.5 2.3 12.1 2.2zm-2.4 6.1c.5 0 .9.4.9.9s-.4.9-.9.9-.9-.4-.9-.9.4-.9.9-.9zm4.6 0c.5 0 .9.4.9.9s-.4.9-.9.9-.9-.4-.9-.9.4-.9.9-.9zM12 12.6c1.3 0 2.4.6 3.1 1.5-.8.5-1.9.8-3.1.8s-2.3-.3-3.1-.8c.7-.9 1.8-1.5 3.1-1.5z"
      />
    </svg>
  );
}

export function ExternalIconLink({ kind }: { kind: "github" | "huggingFace" }) {
  const url = publicExternalUrl(kind);
  if (!url) return null;
  return (
    <a className="ext-icon" href={url} target="_blank" rel="noreferrer" aria-label={externalLinks[kind].label}>
      {kind === "github" ? <GitHubMark /> : <HuggingFaceMark />}
    </a>
  );
}

export function ArticleResourceLinks({ github, huggingFace }: { github?: string; huggingFace?: string }) {
  const links = [
    { key: "github" as const, token: github, label: "View on GitHub" },
    { key: "huggingFace" as const, token: huggingFace, label: "View on Hugging Face" },
  ]
    .map((item) => ({ ...item, href: articleResourceUrl(item.key, item.token) }))
    .filter((item): item is { key: "github" | "huggingFace"; token: string | undefined; label: string; href: string } => Boolean(item.href));
  if (!links.length) return null;
  return (
    <ul className="doc-resources">
      {links.map((item) => (
        <li key={item.key}>
          <a href={item.href} target="_blank" rel="noreferrer">
            {item.label}
          </a>
        </li>
      ))}
    </ul>
  );
}
