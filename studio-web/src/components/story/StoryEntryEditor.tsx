import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import "./story-editor.css";

interface StoryEntry {
  id: string;
  projectId: string;
  title: string;
  entryType: string;
  logline: string;
  shortSummary: string;
  longSummary: string;
  sortOrder: number;
  createdAt: string;
  updatedAt: string;
}

interface StoryEntryEditorProps {
  projectId: string;
  embedded?: boolean;
}

export function StoryEntryEditor({ projectId, embedded = false }: StoryEntryEditorProps) {
  const [entries, setEntries] = useState<StoryEntry[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [publishing, setPublishing] = useState(false);
  const [publishMsg, setPublishMsg] = useState<string>("");
  // Snapshot of Story values at the last explicit "Save to Wiki" publish,
  // keyed by entry id. Used to detect unpublished changes (dirty state).
  // Wiki Story only updates on explicit publish — Story autosave does NOT
  // trigger a Wiki compile.
  const [lastPublished, setLastPublished] = useState<Record<string, { title: string; logline: string; shortSummary: string; longSummary: string }>>({});
  const saveTimerRef = useRef<number | null>(null);
  const loadedRef = useRef(false);

  // Load entries on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await api.storyEntriesList(projectId);
        if (!cancelled) {
          setEntries(list);
          if (list.length > 0) setSelectedId(list[0].id);
          loadedRef.current = true;
        }
      } catch {
        loadedRef.current = true;
      }
    })();
    return () => { cancelled = true; };
  }, [projectId]);

  const selected = entries.find(e => e.id === selectedId);

  // Debounced autosave for a field update
  const scheduleSave = useCallback((entryId: string, field: string, value: string) => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    setSaveState("saving");
    saveTimerRef.current = window.setTimeout(async () => {
      try {
        await api.storyEntriesUpdate(projectId, entryId, { [field]: value });
        setSaveState("saved");
        setTimeout(() => setSaveState("idle"), 2000);
      } catch {
        setSaveState("error");
      }
    }, 700);
  }, [projectId]);

  const updateField = (entryId: string, field: keyof StoryEntry, value: string) => {
    setEntries(prev => prev.map(e => e.id === entryId ? { ...e, [field]: value } : e));
    if (loadedRef.current) scheduleSave(entryId, field, value);
  };

  const handleCreate = async () => {
    try {
      const entry = await api.storyEntriesCreate(projectId, { title: "New Story Entry" });
      setEntries(prev => [...prev, entry]);
      setSelectedId(entry.id);
    } catch { /* ignore */ }
  };

  const handleDelete = async (entryId: string) => {
    try {
      await api.storyEntriesDelete(projectId, entryId);
      setEntries(prev => {
        const next = prev.filter(e => e.id !== entryId);
        if (selectedId === entryId) setSelectedId(next[0]?.id || null);
        return next;
      });
    } catch { /* ignore */ }
  };

  const handleMoveUp = (index: number) => {
    if (index <= 0) return;
    const next = [...entries];
    [next[index - 1], next[index]] = [next[index], next[index - 1]];
    setEntries(next);
    api.storyEntriesReorder(projectId, next.map(e => e.id)).catch(() => {});
  };

  const handleMoveDown = (index: number) => {
    if (index >= entries.length - 1) return;
    const next = [...entries];
    [next[index], next[index + 1]] = [next[index + 1], next[index]];
    setEntries(next);
    api.storyEntriesReorder(projectId, next.map(e => e.id)).catch(() => {});
  };

  // Manual Save to Wiki: the ONLY path that writes Story fields into the Wiki.
  // Story autosave above does NOT trigger a Wiki compile, so editing Story
  // leaves the Wiki at the previously-published version until the creator
  // explicitly publishes here. Blank Story fields map to blank Wiki fields
  // (no conversation fallback — the compiler reads StoryEntry directly).
  const handleSaveToWiki = useCallback(async () => {
    if (!selected) return;
    setPublishing(true);
    setPublishMsg("");
    try {
      await api.compileCoDirectorWiki(projectId, { preserveStoryWording: true });
      // Snapshot the published values so we can detect unpublished changes.
      setLastPublished(prev => ({
        ...prev,
        [selected.id]: {
          title: selected.title,
          logline: selected.logline,
          shortSummary: selected.shortSummary,
          longSummary: selected.longSummary,
        },
      }));
      setPublishMsg("Story saved to Wiki.");
      setTimeout(() => setPublishMsg(""), 3000);
    } catch {
      setPublishMsg("Save to Wiki failed.");
    } finally {
      setPublishing(false);
    }
  }, [projectId, selected]);

  // Dirty-state indicator: Story has unpublished changes vs last publish.
  const hasUnpublishedChanges = (() => {
    if (!selected) return false;
    const snap = lastPublished[selected.id];
    if (!snap) {
      // Never published yet but Story has content → unpublished.
      return Boolean(selected.title || selected.logline || selected.shortSummary || selected.longSummary);
    }
    return (
      snap.title !== selected.title ||
      snap.logline !== selected.logline ||
      snap.shortSummary !== selected.shortSummary ||
      snap.longSummary !== selected.longSummary
    );
  })();

  const baseClass = embedded ? "story-editor story-editor--embedded" : "story-editor";

  if (entries.length === 0 && loadedRef.current) {
    return (
      <div className={baseClass} data-testid="story-editor">
        <div className="story-editor__empty" data-testid="story-empty-state">
          <p>No story entries yet.</p>
          <button type="button" className="primary" onClick={handleCreate} data-testid="story-create-first">
            Create Story
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={baseClass} data-testid="story-editor">
      {/* Entry selector */}
      <div className="story-entry__selector" data-testid="story-entry-selector">
        {entries.map((entry, i) => (
          <div key={entry.id} className={`story-entry__tab ${selectedId === entry.id ? "is-selected" : ""}`}>
            <button
              type="button"
              onClick={() => setSelectedId(entry.id)}
              data-testid={`story-entry-tab-${i}`}
            >
              {entry.title || "Untitled"}
            </button>
            <span className="story-entry__order-controls">
              <button type="button" onClick={() => handleMoveUp(i)} disabled={i === 0}>↑</button>
              <button type="button" onClick={() => handleMoveDown(i)} disabled={i === entries.length - 1}>↓</button>
            </span>
            <button type="button" className="story-entry__delete" onClick={() => handleDelete(entry.id)}>×</button>
          </div>
        ))}
        <button type="button" className="story-entry__add" onClick={handleCreate} data-testid="story-add-entry">
          + ADD STORY ENTRY
        </button>
        <span className="story-editor__status" data-testid="story-save-state">
          {saveState === "saving" ? "Saving..." : saveState === "saved" ? "Saved" : ""}
        </span>
      </div>

      {/* Selected entry form */}
      {selected && (
        <div className="story-entry__form" data-testid="story-entry-form">
          <div className="story-entry__field">
            <label>Story Title</label>
            <input
              type="text"
              value={selected.title}
              onChange={e => updateField(selected.id, "title", e.target.value)}
              placeholder="Story Title"
              data-testid="story-entry-title"
            />
          </div>

          {selected.entryType && (
            <div className="story-entry__field">
              <label>Type</label>
              <select
                value={selected.entryType}
                onChange={e => updateField(selected.id, "entryType", e.target.value)}
                data-testid="story-entry-type"
              >
                <option value="project_story">Project Story</option>
                <option value="episode">Episode</option>
                <option value="chapter">Chapter</option>
                <option value="segment">Segment</option>
                <option value="other">Other</option>
              </select>
            </div>
          )}

          <div className="story-entry__field">
            <label>Logline</label>
            <textarea
              value={selected.logline}
              onChange={e => updateField(selected.id, "logline", e.target.value)}
              placeholder="A concise, compelling summary of your story — one to two sentences."
              rows={3}
              data-testid="story-entry-logline"
            />
          </div>

          <div className="story-entry__field">
            <label>Short Summary</label>
            <textarea
              value={selected.shortSummary}
              onChange={e => updateField(selected.id, "shortSummary", e.target.value)}
              placeholder="A brief overview of the story, characters, and key events."
              rows={5}
              data-testid="story-entry-short-summary"
            />
          </div>

          <div className="story-entry__field">
            <label>Long Summary</label>
            <textarea
              value={selected.longSummary}
              onChange={e => updateField(selected.id, "longSummary", e.target.value)}
              placeholder="A detailed story treatment — full narrative, character arcs, key scenes, and themes."
              rows={12}
              data-testid="story-entry-long-summary"
            />
          </div>

          <div className="story-entry__publish">
            {hasUnpublishedChanges ? (
              <span className="story-entry__dirty" data-testid="story-unpublished-changes">
                Story has unpublished changes
              </span>
            ) : null}
            <button
              type="button"
              className="story-entry__save-wiki"
              onClick={() => void handleSaveToWiki()}
              disabled={publishing}
              data-testid="story-save-to-wiki"
            >
              {publishing ? "Saving to Wiki…" : "Save to Wiki"}
            </button>
            {publishMsg ? (
              <span className="story-entry__publish-msg" data-testid="story-publish-msg">
                {publishMsg}
              </span>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
