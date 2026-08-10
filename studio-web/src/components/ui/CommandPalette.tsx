import { useEffect, useMemo, useState } from "react";
import "./menu.css";

export type CommandItem = {
  id: string;
  title: string;
  meta?: string;
  keywords?: string;
  run: () => void;
};

function fuzzyScore(query: string, target: string): number {
  const q = query.trim().toLowerCase();
  if (!q) return 1;
  const t = target.toLowerCase();
  if (t.includes(q)) return 100 - t.indexOf(q);
  let ti = 0;
  for (const ch of q) {
    ti = t.indexOf(ch, ti);
    if (ti < 0) return 0;
    ti += 1;
  }
  return 10;
}

export function CommandPalette({
  open,
  onClose,
  items,
}: {
  open: boolean;
  onClose: () => void;
  items: CommandItem[];
}) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setActive(0);
    }
  }, [open]);

  const filtered = useMemo(() => {
    return items
      .map((item) => ({
        item,
        score: Math.max(
          fuzzyScore(query, item.title),
          fuzzyScore(query, item.meta || ""),
          fuzzyScore(query, item.keywords || "")
        ),
      }))
      .filter((x) => x.score > 0)
      .sort((a, b) => b.score - a.score)
      .map((x) => x.item)
      .slice(0, 40);
  }, [items, query]);

  useEffect(() => {
    if (active >= filtered.length) setActive(0);
  }, [filtered.length, active]);

  if (!open) return null;

  return (
    <div
      className="ds-command-backdrop"
      role="presentation"
      data-testid="command-palette"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="ds-command"
        role="dialog"
        aria-modal="true"
        aria-label="Quick Search"
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.preventDefault();
            onClose();
          } else if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((i) => Math.min(i + 1, Math.max(filtered.length - 1, 0)));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((i) => Math.max(i - 1, 0));
          } else if (e.key === "Enter") {
            e.preventDefault();
            const hit = filtered[active];
            if (hit) {
              hit.run();
              onClose();
            }
          }
        }}
      >
        <input
          className="ds-command__input"
          autoFocus
          placeholder="Search workspaces, tools, projects…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Quick Search"
        />
        <div className="ds-command__list" role="listbox">
          {filtered.length === 0 ? (
            <div className="ds-command__empty">No matches</div>
          ) : (
            filtered.map((item, index) => (
              <button
                key={item.id}
                type="button"
                role="option"
                aria-selected={index === active}
                className="ds-command__item"
                data-active={index === active}
                onMouseEnter={() => setActive(index)}
                onClick={() => {
                  item.run();
                  onClose();
                }}
              >
                <span className="ds-command__item-title">{item.title}</span>
                {item.meta ? <span className="ds-command__item-meta">{item.meta}</span> : null}
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export function useCommandPaletteShortcut(onOpen: () => void) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey;
      if (mod && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        onOpen();
        return;
      }
      if (mod && e.code === "Space") {
        e.preventDefault();
        onOpen();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onOpen]);
}
