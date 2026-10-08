import { useEffect, useId, useRef, useState } from "react";
import { guideHtml } from "./html";
import { GUIDE_UNAVAILABLE, GUIDE_WELCOME } from "./messages";

type Source = { title: string; heading: string; url: string };
type Turn = { role: "user" | "assistant"; content: string; sources?: Source[] };

const DOCK_KEY = "adept.guide.dock";

type DockPoint = { x: number; y: number };

function readDock(): DockPoint | null {
  try {
    const raw = localStorage.getItem(DOCK_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as DockPoint;
    if (typeof parsed.x !== "number" || typeof parsed.y !== "number") return null;
    return parsed;
  } catch {
    return null;
  }
}

function clampDock(point: DockPoint, width: number, height: number): DockPoint {
  const maxX = Math.max(0, window.innerWidth - width);
  const maxY = Math.max(0, window.innerHeight - height);
  return {
    x: Math.min(Math.max(8, point.x), maxX - 8),
    y: Math.min(Math.max(8, point.y), maxY - 8),
  };
}

const quickActions = [
  ["Getting Started", "How do I get started with Adept UI?"],
  ["Installation", "How do I install Adept UI?"],
  ["AI Video", "How does AI video generation work?"],
  ["Local Models", "Can I run AI video locally?"],
  ["Troubleshooting", "My generation failed. What should I check?"],
] as const;

function pageContext() {
  const path = window.location.pathname;
  const parts = path.split("/").filter(Boolean);
  const url = `${path}${window.location.hash}`.slice(0, 180);
  return {
    url,
    title: document.title.slice(0, 140),
    category: parts[0] === "docs" ? (parts[1] ?? "") : "",
    slug: parts[0] === "docs" ? (parts[2] ?? "") : "",
  };
}

async function readEvents(response: Response, onEvent: (event: string, data: string) => void) {
  const reader = response.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      let event = "message";
      const data: string[] = [];
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) data.push(line.slice(5).trim());
      }
      if (data.length) onEvent(event, data.join(""));
    }
  }
}

export function GuideDock() {
  const titleId = useId();
  const launcherRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [open, setOpen] = useState(false);
  const [dock, setDock] = useState<DockPoint | null>(null);
  const [dragging, setDragging] = useState(false);
  const dragRef = useRef({
    pointerId: -1,
    startX: 0,
    startY: 0,
    originX: 0,
    originY: 0,
    moved: false,
    point: null as DockPoint | null,
  });
  const [draft, setDraft] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const returnFocus = useRef(false);

  useEffect(() => {
    const saved = readDock();
    if (!saved) return;
    const width = launcherRef.current?.offsetWidth ?? 160;
    const height = launcherRef.current?.offsetHeight ?? 52;
    setDock(clampDock(saved, width, height));
  }, []);

  useEffect(() => {
    if (!dock) return;
    const onResize = () => {
      const width = launcherRef.current?.offsetWidth ?? 160;
      const height = launcherRef.current?.offsetHeight ?? 52;
      setDock((current) => (current ? clampDock(current, width, height) : current));
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [dock]);

  useEffect(() => {
    const onOpen = (event: Event) => {
      const detail = (event as CustomEvent<{ draft?: string }>).detail;
      setOpen(true);
      if (detail?.draft) setDraft(detail.draft);
    };
    window.addEventListener("adept-guide-open", onOpen);
    return () => window.removeEventListener("adept-guide-open", onOpen);
  }, []);

  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
      return;
    }
    if (returnFocus.current) {
      returnFocus.current = false;
      launcherRef.current?.focus();
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        returnFocus.current = true;
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const panel = panelRef.current;
    const viewport = window.visualViewport;
    if (!panel || !viewport || window.innerWidth > 720) return;
    const sync = () => {
      panel.style.top = `${viewport.offsetTop}px`;
      panel.style.height = `${viewport.height}px`;
    };
    sync();
    viewport.addEventListener("resize", sync);
    viewport.addEventListener("scroll", sync);
    return () => {
      viewport.removeEventListener("resize", sync);
      viewport.removeEventListener("scroll", sync);
      panel.style.top = "";
      panel.style.height = "";
    };
  }, [open]);

  useEffect(() => () => abortRef.current?.abort(), []);

  function close() {
    returnFocus.current = true;
    setOpen(false);
  }

  async function ask(question: string) {
    const message = question.trim();
    if (!message || busy) return;
    if (message.length > 1200) {
      setTurns((current) => [...current, { role: "assistant", content: "Send a shorter question about Adept UI." }]);
      return;
    }
    const history = turns.slice(-6).map((turn) => ({ role: turn.role, content: turn.content }));
    setDraft("");
    setTurns((current) => [...current, { role: "user", content: message }, { role: "assistant", content: "" }]);
    setBusy(true);
    const abort = new AbortController();
    abortRef.current = abort;
    const write = (update: (turn: Turn) => Turn) => {
      setTurns((current) => {
        const next = current.slice();
        const last = next[next.length - 1];
        if (!last || last.role !== "assistant") return current;
        next[next.length - 1] = update(last);
        return next;
      });
    };
    try {
      const response = await fetch("/api/guide", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history, page: pageContext() }),
        signal: abort.signal,
      });
      if (!response.ok || !response.body) {
        write((turn) => ({ ...turn, content: response.status === 400 ? "Send a shorter question about Adept UI." : GUIDE_UNAVAILABLE }));
        return;
      }
      await readEvents(response, (event, data) => {
        let payload: { text?: string; message?: string; sources?: Source[] } = {};
        try {
          payload = JSON.parse(data) as typeof payload;
        } catch {
          return;
        }
        if (event === "sources" && payload.sources?.length) {
          write((turn) => ({ ...turn, sources: payload.sources?.slice(0, 3) }));
        }
        if (event === "delta" && payload.text) {
          write((turn) => ({ ...turn, content: turn.content + payload.text }));
        }
        if (event === "error" && payload.message) {
          write((turn) => ({ ...turn, content: turn.content || payload.message || GUIDE_UNAVAILABLE }));
        }
      });
      write((turn) => ({ ...turn, content: turn.content || GUIDE_UNAVAILABLE }));
    } catch {
      if (!abort.signal.aborted) write((turn) => ({ ...turn, content: turn.content || GUIDE_UNAVAILABLE }));
    } finally {
      setBusy(false);
    }
  }

  const placeDock = (event: React.PointerEvent<HTMLButtonElement>) => {
    const drag = dragRef.current;
    if (drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (!drag.moved && Math.hypot(dx, dy) < 6) return;
    drag.moved = true;
    const button = event.currentTarget;
    const point = clampDock({ x: drag.originX + dx, y: drag.originY + dy }, button.offsetWidth, button.offsetHeight);
    drag.point = point;
    setDragging(true);
    setDock(point);
  };

  return (
    <>
      <button
        ref={launcherRef}
        type="button"
        className={dragging ? "guide-launcher is-dragging" : "guide-launcher"}
        style={dock ? { left: dock.x, top: dock.y, right: "auto", bottom: "auto" } : undefined}
        aria-expanded={open}
        aria-controls="adept-guide-panel"
        aria-description="Drag to move this button. Click to ask a question."
        hidden={open}
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          const rect = event.currentTarget.getBoundingClientRect();
          dragRef.current = {
            pointerId: event.pointerId,
            startX: event.clientX,
            startY: event.clientY,
            originX: rect.left,
            originY: rect.top,
            moved: false,
            point: dragRef.current.point,
          };
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={placeDock}
        onPointerUp={(event) => {
          if (dragRef.current.pointerId !== event.pointerId) return;
          dragRef.current.pointerId = -1;
          setDragging(false);
          if (dragRef.current.moved && dragRef.current.point) {
            localStorage.setItem(DOCK_KEY, JSON.stringify(dragRef.current.point));
            window.setTimeout(() => {
              dragRef.current.moved = false;
            }, 0);
          }
        }}
        onClick={() => {
          if (dragRef.current.moved) {
            dragRef.current.moved = false;
            return;
          }
          setOpen(true);
        }}
      >
        <img src="/brand/adept-ui-emblem.webp" alt="" width="28" height="28" />
        <span>Ask Adept UI</span>
      </button>
      {open && (
        <section
          ref={panelRef}
          id="adept-guide-panel"
          className="guide-panel"
          role="dialog"
          aria-labelledby={titleId}
        >
          <header className="guide-panel__bar">
            <div>
              <p id={titleId} className="guide-panel__title">
                ADEPT UI GUIDE
              </p>
              <p className="guide-panel__sub">Ask about Adept UI</p>
            </div>
            <button type="button" className="guide-icon" aria-label="Close guide" onClick={close}>
              ×
            </button>
          </header>
          <div className="guide-log" role="log" aria-live="polite" aria-relevant="additions">
            {turns.length === 0 && (
              <div className="guide-welcome">
                <p>{GUIDE_WELCOME}</p>
                <div className="guide-actions">
                  {quickActions.map(([label, question]) => (
                    <button key={label} type="button" onClick={() => void ask(question)}>
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {turns.map((turn, index) => (
              <article key={`${turn.role}-${index}`} className={turn.role === "user" ? "guide-turn guide-turn--user" : "guide-turn"}>
                {turn.role === "assistant" ? (
                  <div className="guide-turn__body" dangerouslySetInnerHTML={{ __html: guideHtml(turn.content) }} />
                ) : (
                  <p>{turn.content}</p>
                )}
                {turn.sources && turn.sources.length > 0 && (
                  <div className="guide-sources">
                    <p>Sources</p>
                    <ul>
                      {turn.sources.map((source) => (
                        <li key={source.url}>
                          <a href={source.url}>
                            {source.title}
                            {source.heading ? ` — ${source.heading}` : ""}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </article>
            ))}
          </div>
          <form
            className="guide-form"
            onSubmit={(event) => {
              event.preventDefault();
              void ask(draft);
            }}
          >
            <label className="sr-only" htmlFor="adept-guide-input">
              Ask about Adept UI
            </label>
            <textarea
              ref={inputRef}
              id="adept-guide-input"
              rows={2}
              maxLength={1200}
              value={draft}
              placeholder="Ask about Adept UI..."
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void ask(draft);
                }
              }}
            />
            <button type="submit" disabled={busy || !draft.trim()}>
              Send
            </button>
          </form>
        </section>
      )}
    </>
  );
}
