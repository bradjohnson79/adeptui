import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import type { SaveState } from "../scriptwriter/types";
import {
  defaultStoryTitle,
  emitStoryCanonicalChanged,
  pickPrimaryStoryEntry,
  subscribeStoryCanonicalChanged,
  type CanonicalStoryEntry,
} from "./canonicalStory";
import { StoryRichBody } from "./StoryRichBody";

export type StoryDocumentHandle = {
  entryId: string;
  title: string;
  rename: (next: string) => Promise<void>;
};

type Props = {
  projectId: string;
  projectName: string;
  onSaveState?: (state: SaveState) => void;
  onTitleChange?: (title: string) => void;
  onReady?: (handle: StoryDocumentHandle) => void;
  source?: "scriptwriter" | "express";
};

export function StoryDocumentEditor({
  projectId,
  projectName,
  onSaveState,
  onTitleChange,
  onReady,
  source = "scriptwriter",
}: Props) {
  const [entry, setEntry] = useState<CanonicalStoryEntry | null>(null);
  const [error, setError] = useState<string | null>(null);
  const entryRef = useRef<CanonicalStoryEntry | null>(null);
  const saveTimer = useRef<number | null>(null);
  const loaded = useRef(false);
  const ignoreRemote = useRef(false);
  const onReadyRef = useRef(onReady);
  const onTitleChangeRef = useRef(onTitleChange);
  const onSaveStateRef = useRef(onSaveState);
  onReadyRef.current = onReady;
  onTitleChangeRef.current = onTitleChange;
  onSaveStateRef.current = onSaveState;

  const applyEntry = useCallback((next: CanonicalStoryEntry) => {
    entryRef.current = next;
    setEntry(next);
    onTitleChangeRef.current?.(next.title || defaultStoryTitle(projectName));
  }, [projectName]);

  const persist = useCallback(
    async (patch: { title?: string; longSummary?: string }) => {
      const current = entryRef.current;
      if (!current) return;
      onSaveStateRef.current?.("saving");
      const saved = (await api.storyEntriesUpdate(projectId, current.id, patch)) as CanonicalStoryEntry;
      applyEntry(saved);
      emitStoryCanonicalChanged({
        projectId,
        entryId: saved.id,
        title: saved.title,
        longSummary: saved.longSummary,
        source,
      });
      onSaveStateRef.current?.("saved");
    },
    [applyEntry, projectId, source],
  );

  const rename = useCallback(
    async (next: string) => {
      const title = next.trim() || defaultStoryTitle(projectName);
      setEntry((prev) => (prev ? { ...prev, title } : prev));
      onTitleChangeRef.current?.(title);
      try {
        await persist({ title });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Story save failed");
        onSaveStateRef.current?.("save_failed");
        throw err;
      }
    },
    [persist, projectName],
  );

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const list = (await api.storyEntriesList(projectId)) as CanonicalStoryEntry[];
        const existing = pickPrimaryStoryEntry(list);
        const primary =
          existing ||
          ((await api.storyEntriesEnsure(projectId, {
            title: defaultStoryTitle(projectName),
          })) as CanonicalStoryEntry);
        if (cancelled) return;
        applyEntry(primary);
        loaded.current = true;
        onSaveStateRef.current?.("saved");
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not open the story document.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applyEntry, projectId, projectName]);

  useEffect(() => {
    const current = entry;
    if (!current) return;
    onReadyRef.current?.({
      entryId: current.id,
      title: current.title,
      rename,
    });
  }, [entry, rename]);

  useEffect(
    () =>
      subscribeStoryCanonicalChanged((detail) => {
        if (detail.projectId !== projectId) return;
        if (detail.source === source) return;
        if (ignoreRemote.current) return;
        const current = entryRef.current;
        if (!current || current.id !== detail.entryId) return;
        applyEntry({ ...current, title: detail.title, longSummary: detail.longSummary });
      }),
    [applyEntry, projectId, source],
  );

  const scheduleBody = (html: string) => {
    if (!loaded.current) return;
    onSaveStateRef.current?.("unsaved");
    if (saveTimer.current) window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => {
      ignoreRemote.current = true;
      void persist({ longSummary: html })
        .catch((err) => {
          setError(err instanceof Error ? err.message : "Story save failed");
          onSaveStateRef.current?.("save_failed");
        })
        .finally(() => {
          window.setTimeout(() => {
            ignoreRemote.current = false;
          }, 400);
        });
    }, 700);
  };

  if (error && !entry) {
    return (
      <div className="sw-page sw-story-page" data-testid="scriptwriter-story-document">
        <p className="muted">{error}</p>
      </div>
    );
  }

  if (!entry) {
    return (
      <div className="sw-page sw-story-page" data-testid="scriptwriter-story-document">
        <p className="muted">Opening story document…</p>
      </div>
    );
  }

  return (
    <div className="sw-page sw-story-page" data-testid="scriptwriter-story-document" aria-label="Story document">
      <p className="eyebrow sw-story-page__label">Story document</p>
      <input
        className="sw-story-page__title"
        data-testid="scriptwriter-story-page-title"
        value={entry.title}
        onChange={(e) => {
          const title = e.target.value;
          setEntry((prev) => (prev ? { ...prev, title } : prev));
          onTitleChangeRef.current?.(title);
          onSaveStateRef.current?.("unsaved");
          if (saveTimer.current) window.clearTimeout(saveTimer.current);
          saveTimer.current = window.setTimeout(() => {
            void persist({ title: title.trim() || defaultStoryTitle(projectName) }).catch((err) => {
              setError(err instanceof Error ? err.message : "Story save failed");
              onSaveStateRef.current?.("save_failed");
            });
          }, 700);
        }}
        placeholder={defaultStoryTitle(projectName)}
        aria-label="Story title"
      />
      <p className="muted sw-story-page__hint">
        Synopsis, world, characters, and arcs. Dialogue and scene pages stay in Script.
      </p>
      {error ? <p className="muted" role="alert">{error}</p> : null}
      <StoryRichBody
        html={entry.longSummary}
        testId="scriptwriter-story-editor"
        onChange={(html) => {
          setEntry((prev) => (prev ? { ...prev, longSummary: html } : prev));
          scheduleBody(html);
        }}
      />
    </div>
  );
}
