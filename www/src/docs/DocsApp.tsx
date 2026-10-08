import { useEffect, useMemo, useState, type ReactNode } from "react";
import { site } from "../content";
import { ArticleResourceLinks, ExternalIconLink } from "../components/ExternalLinks";
import { resolveSiteUrl } from "../seo";
import { categoryById, docCategories } from "./categories";
import { articlesIn, findArticle, findHidden, publishedArticles, relatedArticles, searchDocs } from "./catalog";
import type { DocArticle, DocBlock } from "./types";
import "../styles/docs.css";

const difficultyLabel = {
  start: "Start here",
  practice: "Hands on",
  technical: "Technical",
} as const;

const origin = resolveSiteUrl(import.meta.env.VITE_SITE_URL);

function routeParts(pathname: string): string[] {
  return pathname.replace(/\/+$/, "").split("/").filter(Boolean);
}

function upsertMeta(attr: "name" | "property", key: string, content: string) {
  let node = document.head.querySelector(`meta[${attr}="${key}"]`);
  if (!node) {
    node = document.createElement("meta");
    node.setAttribute(attr, key);
    document.head.appendChild(node);
  }
  node.setAttribute("content", content);
}

function upsertLink(rel: string, href: string | null) {
  const selector = `link[rel="${rel}"][data-docs="true"]`;
  const existing = document.head.querySelector(selector);
  if (!href) {
    existing?.remove();
    return;
  }
  const node = existing ?? document.createElement("link");
  node.setAttribute("rel", rel);
  node.setAttribute("data-docs", "true");
  node.setAttribute("href", href);
  if (!existing) document.head.appendChild(node);
}

function jsonLd(article: DocArticle | null, crumbs: { name: string; path: string }[]) {
  const graph: Record<string, unknown>[] = [
    {
      "@type": "BreadcrumbList",
      itemListElement: crumbs.map((crumb, index) => ({
        "@type": "ListItem",
        position: index + 1,
        name: crumb.name,
        ...(origin ? { item: `${origin}${crumb.path}` } : {}),
      })),
    },
  ];
  if (article) {
    graph.push({
      "@type": "TechArticle",
      headline: article.title,
      description: article.summary,
      ...(origin ? { url: `${origin}${article.href}`, mainEntityOfPage: `${origin}${article.href}` } : {}),
    });
  }
  return JSON.stringify({ "@context": "https://schema.org", "@graph": graph }).replaceAll("<", "\\u003c");
}

function ArticleBody({ blocks }: { blocks: DocBlock[] }) {
  return (
    <>
      {blocks.map((block, index) => {
        if (block.type === "h") {
          const Tag = block.level === 2 ? "h2" : "h3";
          return (
            <Tag id={block.id} key={block.id}>
              {block.text}
            </Tag>
          );
        }
        if (block.type === "p") return <p key={index} dangerouslySetInnerHTML={{ __html: block.html }} />;
        if (block.type === "list") {
          const Tag = block.ordered ? "ol" : "ul";
          return (
            <Tag key={index}>
              {block.items.map((item) => (
                <li key={item} dangerouslySetInnerHTML={{ __html: item }} />
              ))}
            </Tag>
          );
        }
        if (block.type === "pre") {
          return (
            <pre key={index}>
              <code>{block.code}</code>
            </pre>
          );
        }
        if (block.type === "quote") {
          return <blockquote className={`callout callout--${block.kind}`} key={index} dangerouslySetInnerHTML={{ __html: block.html }} />;
        }
        if (block.type === "img") {
          return (
            <figure className="docs-figure" key={block.src}>
              <img src={block.src} alt={block.alt} />
              <figcaption>{block.alt}</figcaption>
            </figure>
          );
        }
        return (
          <table key={index}>
            <thead>
              <tr>
                {block.headers.map((header) => (
                  <th key={header}>{header}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row) => (
                <tr key={row.join("|")}>
                  {row.map((cell) => (
                    <td key={cell}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        );
      })}
    </>
  );
}

function ArticleCard({ article }: { article: DocArticle }) {
  const category = categoryById.get(article.category);
  return (
    <a className="doc-card" href={article.href}>
      <p className="doc-card__meta">
        <span>{category?.title}</span>
        <span>{difficultyLabel[article.difficulty]}</span>
        <span>{article.minutes} min</span>
      </p>
      <h3>{article.title}</h3>
      <p>{article.summary}</p>
      {article.tags.length > 0 && (
        <ul className="doc-tags">
          {article.tags.slice(0, 4).map((tag) => (
            <li key={tag}>{tag}</li>
          ))}
        </ul>
      )}
    </a>
  );
}

export function DocsApp() {
  const pathname = window.location.pathname;
  const parts = routeParts(pathname);
  const categoryId = parts[1] ?? "";
  const slug = parts[2] ?? "";
  const category = categoryById.get(categoryId);
  const article = category && slug ? findArticle(categoryId, slug) : undefined;
  const hidden = category && slug && !article ? findHidden(categoryId, slug) : undefined;
  const [query, setQuery] = useState("");
  const [navOpen, setNavOpen] = useState(false);
  const results = useMemo(() => searchDocs(publishedArticles, query), [query]);
  const searching = query.trim().length > 1;

  const crumbs = useMemo(() => {
    const items = [{ name: "Docs", path: "/docs" }];
    if (category) items.push({ name: category.title, path: `/docs/${category.id}` });
    if (article) items.push({ name: article.title, path: article.href });
    return items;
  }, [article, category]);

  useEffect(() => {
    const title = article?.seoTitle ?? (category ? `${category.title} — Adept UI Docs` : "Adept UI Documentation");
    const description =
      article?.seoDescription ??
      category?.summary ??
      "Guides for Adept UI: projects, Co-Director, storyboard, generation, Timeline, and MAGI.";
    const previousTitle = document.title;
    document.title = title;
    upsertMeta("name", "description", description);
    upsertMeta("property", "og:title", title);
    upsertMeta("property", "og:description", description);
    upsertMeta("name", "twitter:title", title);
    upsertMeta("name", "twitter:description", description);
    const canonical = origin ? `${origin}${article?.href ?? (category ? `/docs/${category.id}` : "/docs")}` : null;
    upsertLink("canonical", canonical);
    if (canonical) upsertMeta("property", "og:url", canonical);
    let script = document.getElementById("docs-jsonld");
    if (!script) {
      script = document.createElement("script");
      script.id = "docs-jsonld";
      script.setAttribute("type", "application/ld+json");
      document.head.appendChild(script);
    }
    script.textContent = jsonLd(article ?? null, crumbs);
    return () => {
      document.title = previousTitle || site.title;
      script?.remove();
      upsertLink("canonical", null);
    };
  }, [article, category, crumbs]);

  const popular = ["what-is-adept-ui", "your-first-project", "what-is-co-director", "what-is-timeline", "ai-film-from-scratch"]
    .map((id) => publishedArticles.find((item) => item.slug === id))
    .filter((item): item is DocArticle => Boolean(item));
  const recent = [...publishedArticles].sort((a, b) => b.updated.localeCompare(a.updated) || a.title.localeCompare(b.title)).slice(0, 6);

  let main: ReactNode;
  if (searching) {
    main = (
      <>
        <h1>Search results</h1>
        <p className="dek">
          {results.length === 0 ? "No published article matches that search." : `${results.length} published ${results.length === 1 ? "article" : "articles"}.`}
        </p>
        <div className="doc-results">
          {results.map((hit) => (
            <a key={hit.article.href} href={hit.article.href}>
              <p className="doc-card__meta">
                <span>{categoryById.get(hit.article.category)?.title}</span>
              </p>
              <h2>{hit.article.title}</h2>
              <p>{hit.article.summary}</p>
              <p className="snippet">{hit.snippet}</p>
            </a>
          ))}
        </div>
      </>
    );
  } else if (parts.length === 1) {
    main = (
      <>
        <p className="eyebrow">Documentation</p>
        <h1>Adept UI documentation</h1>
        <p className="dek">
          Practical guides for making a film inside Adept UI. Start with the project, then follow a shot from planning through generation, Timeline, and MAGI.
        </p>
        <section className="docs-band" aria-labelledby="start-here">
          <h2 id="start-here">Start here</h2>
          <div className="doc-grid">
            {popular.slice(0, 4).map((item) => (
              <ArticleCard article={item} key={item.href} />
            ))}
          </div>
        </section>
        <section className="docs-band" aria-labelledby="categories">
          <h2 id="categories">Categories</h2>
          <div className="doc-grid">
            {docCategories.map((item) => (
              <a className="doc-card" href={`/docs/${item.id}`} key={item.id}>
                <p className="doc-card__meta">
                  <span>{articlesIn(item.id).length} articles</span>
                </p>
                <h3>{item.title}</h3>
                <p>{item.summary}</p>
              </a>
            ))}
          </div>
        </section>
        <section className="docs-split">
          <div>
            <h2>Popular guides</h2>
            <ul className="doc-links">
              {popular.map((item) => (
                <li key={item.href}>
                  <a href={item.href}>{item.title}</a>
                  <span>{item.summary}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h2>When something fails</h2>
            <p>A stuck or failed generation is a production problem, not a reason to start a second project.</p>
            <a className="docs-text-link" href="/docs/troubleshooting/troubleshooting-generation">
              Troubleshooting generation
            </a>
            <h2>For developers</h2>
            <p>A public map of the product: the interface, the studio service, and the model you actually selected.</p>
            <a className="docs-text-link" href="/docs/developer/architecture-overview">
              Architecture overview
            </a>
          </div>
        </section>
        <section className="docs-band">
          <h2>Recent documentation</h2>
          <ul className="doc-links">
            {recent.map((item) => (
              <li key={item.href}>
                <a href={item.href}>{item.title}</a>
                <span>{item.updated ? `Updated ${item.updated}` : categoryById.get(item.category)?.title}</span>
              </li>
            ))}
          </ul>
        </section>
      </>
    );
  } else if (category && !slug) {
    const articles = articlesIn(category.id);
    main = (
      <>
        <h1>{category.title}</h1>
        <p className="dek">{category.summary}</p>
        <div className="doc-grid">
          {articles.map((item) => (
            <ArticleCard article={item} key={item.href} />
          ))}
        </div>
      </>
    );
  } else if (article) {
    const related = relatedArticles(article);
    main = (
      <article>
        <p className="doc-card__meta">
          <span>{difficultyLabel[article.difficulty]}</span>
          <span>{article.minutes} min read</span>
          {article.updated && <span>Updated {article.updated}</span>}
        </p>
        <h1>{article.title}</h1>
        <p className="dek">{article.summary}</p>
        {article.tags.length > 0 && (
          <ul className="doc-tags">
            {article.tags.map((tag) => (
              <li key={tag}>{tag}</li>
            ))}
          </ul>
        )}
        <ArticleResourceLinks github={article.github} huggingFace={article.huggingFace} />
        <p className="docs-ask">
          <button
            type="button"
            onClick={() => {
              window.dispatchEvent(new CustomEvent("adept-guide-open", { detail: { draft: "Why would I use this?" } }));
            }}
          >
            Ask about this article
          </button>
        </p>
        <ArticleBody blocks={article.blocks} />
        {related.length > 0 && (
          <section className="docs-related" aria-labelledby="related-guides">
            <h2 id="related-guides">Related guides</h2>
            <div className="doc-grid">
              {related.map((item) => (
                <ArticleCard article={item} key={item.href} />
              ))}
            </div>
          </section>
        )}
      </article>
    );
  } else {
    main = (
      <>
        <h1>{hidden ? "This article is not published" : "This page is not in the documentation"}</h1>
        <p className="dek">
          {hidden
            ? "The notes for this topic are still under review, so they are not shown here."
            : "That address does not match a published guide."}
        </p>
        <a className="docs-text-link" href="/docs">
          Back to documentation
        </a>
      </>
    );
  }

  return (
    <div className="docs">
      <a className="skip" href="#docs-main">
        Skip to content
      </a>
      <header className="docs-top">
        <a className="docs-brand" href="/">
          ADEPT UI <span className="beta-badge">Beta</span>
        </a>
        <a href="/docs">Docs</a>
        <a href="/contact">Contact</a>
        <form
          role="search"
          onSubmit={(event) => {
            event.preventDefault();
          }}
        >
          <label htmlFor="docs-search">Search documentation</label>
          <input
            id="docs-search"
            type="search"
            value={query}
            placeholder="Search guides"
            onChange={(event) => setQuery(event.target.value)}
          />
        </form>
        <ExternalIconLink kind="github" />
        <ExternalIconLink kind="huggingFace" />
        <button type="button" className="docs-nav-toggle" aria-expanded={navOpen} aria-controls="docs-nav" onClick={() => setNavOpen((open) => !open)}>
          {navOpen ? "Close" : "Guides"}
        </button>
      </header>
      <div className="docs-shell">
        <nav id="docs-nav" className={navOpen ? "docs-nav is-open" : "docs-nav"} aria-label="Documentation">
          {docCategories.map((item) => (
            <details key={item.id} open={item.id === categoryId || (!categoryId && item.group === "start")}>
              <summary>
                <a href={`/docs/${item.id}`}>{item.title}</a>
              </summary>
              <ul>
                {articlesIn(item.id).map((itemArticle) => (
                  <li key={itemArticle.href}>
                    <a href={itemArticle.href} aria-current={itemArticle.href === article?.href ? "page" : undefined}>
                      {itemArticle.title}
                    </a>
                  </li>
                ))}
              </ul>
            </details>
          ))}
        </nav>
        <main id="docs-main">
          <nav className="crumbs" aria-label="Breadcrumb">
            <ol>
              {crumbs.map((crumb, index) => (
                <li key={crumb.path}>
                  {index < crumbs.length - 1 ? <a href={crumb.path}>{crumb.name}</a> : <span aria-current="page">{crumb.name}</span>}
                </li>
              ))}
            </ol>
          </nav>
          {main}
        </main>
        <aside className="docs-toc" aria-label="On this page">
          {article && article.headings.length > 0 && (
            <>
              <p>On this page</p>
              <ol>
                {article.headings
                  .filter((heading) => heading.level === 2)
                  .map((heading) => (
                    <li key={heading.id}>
                      <a href={`#${heading.id}`}>{heading.text}</a>
                    </li>
                  ))}
              </ol>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
