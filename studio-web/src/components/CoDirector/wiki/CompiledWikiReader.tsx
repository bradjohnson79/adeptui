import { useEffect, useMemo, useState } from "react";
import type { CoDirectorProjectWiki } from "../../../api";
import { Button } from "../../ui";

type TocNode = {
  key: string;
  label: string;
  count: number;
  children?: { id?: string; label: string; pageId?: string }[];
};

type Page = NonNullable<CoDirectorProjectWiki["compiledPages"]>[number];

const TOC_EXPAND_KEY = "adept_wiki_toc_expand";

function loadExpand(): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem(TOC_EXPAND_KEY) || "{}") as Record<string, boolean>;
  } catch {
    return {};
  }
}

function saveExpand(state: Record<string, boolean>) {
  try {
    localStorage.setItem(TOC_EXPAND_KEY, JSON.stringify(state));
  } catch {
    /* ignore */
  }
}

export function CompiledWikiReader({
  wiki,
  onOpenCasting,
  onCorrect,
  onRefineStorySummary,
  onDevelopStory,
  onPageChange,
}: {
  wiki: CoDirectorProjectWiki;
  onOpenCasting?: (characterName: string) => void;
  onCorrect?: (page: Page) => void;
  onRefineStorySummary?: () => void;
  onDevelopStory?: () => void;
  onPageChange?: (page: Page | null) => void;
}) {
  const pages = wiki.compiledPages || [];
  const toc = (wiki.compiledToc || wiki.professionalToc || []) as TocNode[];
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expand, setExpand] = useState<Record<string, boolean>>(() => ({
    projectOverview: true,
    story: true,
    characters: true,
    ...loadExpand(),
  }));

  const pageById = useMemo(() => {
    const map = new Map<string, Page>();
    for (const p of pages) map.set(p.pageId, p);
    return map;
  }, [pages]);

  const landing = useMemo(() => {
    const overview = pages.find((p) => p.pageType === "PROJECT");
    const story = pages.find((p) => p.pageType === "STORY");
    const characters = pages.filter((p) => p.pageType === "CHARACTER");
    const episodes = pages.filter((p) => p.pageType === "EPISODE");
    return { overview, story, characters, episodes };
  }, [pages]);

  useEffect(() => {
    if (selectedId && !pageById.has(selectedId)) setSelectedId(null);
  }, [selectedId, pageById]);

  const selected = selectedId ? pageById.get(selectedId) : null;

  // Lift the current page up so Refine Wiki can target it contextually.
  useEffect(() => {
    onPageChange?.(selected ?? null);
  }, [selected, onPageChange]);

  const toggle = (key: string) => {
    setExpand((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      saveExpand(next);
      return next;
    });
  };

  return (
    <div className="compiled-wiki-reader" data-testid="compiled-wiki-reader">
      <div className="compiled-wiki-layout" style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: "1.25rem" }}>
        <nav className="compiled-wiki-toc" aria-label="Table of Contents" data-testid="compiled-wiki-toc">
          <div className="muted" style={{ fontSize: "0.7rem", letterSpacing: "0.06em", marginBottom: "0.5rem" }}>
            TABLE OF CONTENTS
          </div>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {toc.map((node) => {
              const open = expand[node.key] !== false;
              const hasChildren = Boolean(node.children?.length);
              return (
                <li key={node.key} style={{ marginBottom: "0.35rem" }}>
                  <button
                    type="button"
                    className="compiled-wiki-toc-root"
                    data-testid={`wiki-toc-${node.key}`}
                    onClick={() => {
                      if (hasChildren) toggle(node.key);
                      const page =
                        node.key === "projectOverview"
                          ? pages.find((p) => p.pageType === "PROJECT")
                          : node.key === "story"
                            ? pages.find((p) => p.pageType === "STORY")
                            : null;
                      if (page) setSelectedId(page.pageId);
                      if (node.key === "characters" || node.key === "episodesAndScenes") setSelectedId(null);
                    }}
                    style={{
                      background: "none",
                      border: "none",
                      color: "inherit",
                      cursor: "pointer",
                      padding: 0,
                      fontWeight: 600,
                      textAlign: "left",
                    }}
                  >
                    {hasChildren ? (open ? "▾ " : "▸ ") : ""}
                    {node.label}
                    {typeof node.count === "number" && node.count > 0 ? ` (${node.count})` : ""}
                  </button>
                  {hasChildren && open ? (
                    <ul style={{ listStyle: "none", padding: "0.25rem 0 0 0.9rem", margin: 0 }}>
                      {node.children!.map((child) => (
                        <li key={child.id || child.label}>
                          <button
                            type="button"
                            data-testid={`wiki-toc-child-${child.id || child.label}`}
                            onClick={() => setSelectedId(child.id || child.pageId || null)}
                            style={{
                              background: "none",
                              border: "none",
                              color: "inherit",
                              cursor: "pointer",
                              padding: "0.15rem 0",
                              textAlign: "left",
                              opacity: 0.9,
                            }}
                          >
                            {child.label}
                          </button>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </nav>

        <article className="compiled-wiki-article" data-testid="compiled-wiki-article">
          {selected ? (
            <PageView
              page={selected}
              onOpenCasting={onOpenCasting}
              onCorrect={onCorrect}
              onRefineStorySummary={onRefineStorySummary}
              onDevelopStory={onDevelopStory}
              onBack={() => setSelectedId(null)}
            />
          ) : (
            <LandingView
              overview={landing.overview}
              story={landing.story}
              characters={landing.characters}
              episodes={landing.episodes}
              storySummary={wiki.compiledStorySummary}
              onOpenPage={(id) => setSelectedId(id)}
            />
          )}
        </article>
      </div>
    </div>
  );
}

function LandingView({
  overview,
  story,
  characters,
  episodes,
  storySummary,
  onOpenPage,
}: {
  overview?: Page;
  story?: Page;
  characters: Page[];
  episodes: Page[];
  storySummary?: CoDirectorProjectWiki["compiledStorySummary"];
  onOpenPage: (id: string) => void;
}) {
  return (
    <div data-testid="compiled-wiki-landing">
      {overview ? (
        <section style={{ marginBottom: "1.5rem" }} data-testid="wiki-section-overview">
          <h2 style={{ marginTop: 0 }}>{overview.title}</h2>
          <p style={{ lineHeight: 1.55, fontSize: "1.05rem" }}>{overview.summary || overview.sections?.[0]?.body}</p>
        </section>
      ) : null}

      <section style={{ marginBottom: "1.5rem" }} data-testid="wiki-section-story">
        <h2>Story</h2>
        {storySummary?.logline ? (
          <>
            <h3 style={{ fontSize: "0.95rem", marginBottom: "0.25rem" }}>Logline</h3>
            <p style={{ lineHeight: 1.5 }}>{storySummary.logline}</p>
          </>
        ) : null}
        {storySummary?.shortSummary ? (
          <>
            <h3 style={{ fontSize: "0.95rem", marginBottom: "0.25rem" }}>Short Summary</h3>
            <p style={{ lineHeight: 1.5 }}>{storySummary.shortSummary}</p>
          </>
        ) : null}
        {storySummary?.longSummary ? (
          <>
            <h3 style={{ fontSize: "0.95rem", marginBottom: "0.25rem" }}>Long Summary</h3>
            <p style={{ lineHeight: 1.5 }}>{storySummary.longSummary}</p>
          </>
        ) : null}
        {storySummary?.themes?.length ? (
          <>
            <h3 style={{ fontSize: "0.95rem", marginBottom: "0.25rem" }}>Themes</h3>
            <ul>
              {storySummary.themes.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          </>
        ) : null}
        {story ? (
          <Button variant="compact" onClick={() => onOpenPage(story.pageId)}>
            Open Story page
          </Button>
        ) : null}
      </section>

      {episodes.length ? (
        <section style={{ marginBottom: "1.5rem" }} data-testid="wiki-section-episodes">
          <h2>Episodes</h2>
          <ul style={{ listStyle: "none", padding: 0 }}>
            {episodes.map((ep) => (
              <li key={ep.pageId} style={{ marginBottom: "0.75rem" }}>
                <button
                  type="button"
                  data-testid={`wiki-episode-link-${ep.pageId}`}
                  onClick={() => onOpenPage(ep.pageId)}
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--accent, #6cb6ff)",
                    cursor: "pointer",
                    padding: 0,
                    fontWeight: 600,
                    fontSize: "1rem",
                  }}
                >
                  {ep.title}
                </button>
                {ep.summary ? <p className="muted" style={{ margin: "0.25rem 0 0", lineHeight: 1.45 }}>{ep.summary}</p> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section data-testid="wiki-section-characters">
        <h2>Characters</h2>
        {characters.length ? (
          <ul data-testid="wiki-character-list">
            {characters.map((c) => (
              <li key={c.pageId}>
                <button
                  type="button"
                  data-testid={`wiki-character-link-${c.pageId}`}
                  onClick={() => onOpenPage(c.pageId)}
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--accent, #6cb6ff)",
                    cursor: "pointer",
                    padding: "0.15rem 0",
                    fontSize: "1rem",
                  }}
                >
                  {c.title}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Characters appear as Co-Director recognizes them.</p>
        )}
      </section>
    </div>
  );
}

function PageView({
  page,
  onOpenCasting,
  onCorrect,
  onRefineStorySummary,
  onDevelopStory,
  onBack,
}: {
  page: Page;
  onOpenCasting?: (name: string) => void;
  onCorrect?: (page: Page) => void;
  onRefineStorySummary?: () => void;
  onDevelopStory?: () => void;
  onBack: () => void;
}) {
  return (
    <div data-testid={`wiki-page-${page.pageId}`}>
      <Button variant="compact" onClick={onBack} data-testid="wiki-page-back">
        ← Wiki
      </Button>
      <h2 style={{ marginBottom: "0.35rem" }}>{page.title}</h2>
      {page.summary ? <p className="muted" style={{ lineHeight: 1.5 }}>{page.summary}</p> : null}
      {(page.sections || [])
        .filter((s) => (s.body && s.body.trim()) || (s.bullets && s.bullets.length))
        .map((sec) => {
          const isSummarySection =
            page.pageType === "STORY" && /logline|short summary|long summary/i.test(sec.title || "");
          return (
            <section key={sec.id} style={{ marginTop: "1.1rem" }} data-testid={`wiki-section-${sec.id}`}>
              <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
                <h3 style={{ fontSize: "1rem", marginBottom: "0.35rem" }}>{sec.title}</h3>
                {isSummarySection && onCorrect ? (
                  <Button
                    variant="ghost"
                    compact
                    data-testid={`wiki-refine-section-${sec.id}`}
                    onClick={() => onCorrect(page)}
                  >
                    Refine
                  </Button>
                ) : null}
              </div>
              {sec.body ? <p style={{ lineHeight: 1.55 }}>{sec.body}</p> : null}
              {sec.bullets?.length ? (
                <ul>
                  {sec.bullets.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              ) : null}
              {(sec as { developStoryAction?: boolean }).developStoryAction && onDevelopStory ? (
                <div style={{ marginTop: "0.75rem" }}>
                  <Button
                    variant="compact"
                    data-testid="wiki-develop-story"
                    onClick={onDevelopStory}
                  >
                    Develop the story
                  </Button>
                </div>
              ) : null}
            </section>
          );
        })}
      {page.questionsToExplore?.length ? (
        <section style={{ marginTop: "1.25rem" }} data-testid="wiki-questions">
          <h3 style={{ fontSize: "1rem" }}>Questions to Explore</h3>
          <ul>
            {page.questionsToExplore.slice(0, 5).map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
        </section>
      ) : null}
      <div className="row" style={{ gap: "0.5rem", marginTop: "1rem", flexWrap: "wrap" }}>
        {page.pageType === "CHARACTER" && onOpenCasting ? (
          <Button
            variant="compact"
            data-testid="wiki-view-casting"
            onClick={() => onOpenCasting(page.title)}
          >
            View Casting
          </Button>
        ) : null}
        {page.pageType === "STORY" && onRefineStorySummary ? (
          <Button
            variant="compact"
            data-testid="wiki-refine-story-summary"
            onClick={onRefineStorySummary}
          >
            Refine Story Summary
          </Button>
        ) : null}
        {onCorrect ? (
          <Button variant="compact" data-testid="wiki-correct" onClick={() => onCorrect(page)}>
            Correct with Co-Director
          </Button>
        ) : null}
      </div>
    </div>
  );
}
