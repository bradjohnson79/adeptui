import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";

export type ScenePromptTemplate = {
  id: string;
  projectId: string;
  sourceSceneId?: string;
  name: string;
  promptText: string;
  generatorFamily?: string;
  generatorFamilyUsed?: string;
  generatorId?: string;
  createdAt?: string;
  updatedAt?: string;
  promptTextLength?: number;
};

/**
 * Timeline Inspector / Timed Prompt modal chrome for Scene Prompt Template Library.
 * Server-authoritative CRUD; exact prompt_text preserve; dirty confirm on Load.
 */
export function ScenePromptTemplateBar({
  projectId,
  workingText,
  isDirty,
  onLoadText,
  generatorFamily,
  generatorId,
  sourceSceneId,
  suggestedName,
  testIdPrefix = "scene-prompt-template",
}: {
  projectId: string;
  workingText: string;
  isDirty: boolean;
  onLoadText: (text: string) => void | Promise<void>;
  generatorFamily?: string | null;
  generatorId?: string | null;
  sourceSceneId?: string | null;
  suggestedName?: string | null;
  testIdPrefix?: string;
}) {
  const [templates, setTemplates] = useState<ScenePromptTemplate[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const refresh = useCallback(async () => {
    if (!projectId) return;
    try {
      const rows = await api.scenePromptTemplatesList(projectId);
      setTemplates(Array.isArray(rows) ? rows : []);
      setError(null);
    } catch (err: any) {
      setError(err?.message || "Failed to load templates");
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [menuOpen]);

  const selected = templates.find((t) => t.id === selectedId) || null;

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      await fn();
      setStatus(label);
      await refresh();
    } catch (err: any) {
      setError(err?.message || label);
    } finally {
      setBusy(false);
    }
  };

  const onLoad = async () => {
    if (!selectedId) return;
    const row =
      selected ||
      (await api.scenePromptTemplatesGet(projectId, selectedId));
    const text = row?.promptText ?? "";
    // Dirty = draft dirty OR working copy already diverged from selected template
    // (covers post-idle-autosave case where isDirty cleared).
    const divergesFromTemplate = workingText !== text;
    if (isDirty || divergesFromTemplate) {
      const ok = window.confirm(
        "Timed Prompt differs from the selected template.\n\nReplace working copy with template text?\n\nOK = Replace\nCancel = keep current text",
      );
      if (!ok) return;
    }
    await onLoadText(text);
    setStatus(`Loaded "${row?.name || "template"}" (exact)`);
  };

  const defaultSaveName =
    (suggestedName && suggestedName.trim()) ||
    selected?.name ||
    "Timed Prompt template";

  const onSave = () => {
    const name = window.prompt("Template name", defaultSaveName);
    if (!name || !name.trim()) return;
    void run("Saved", async () => {
      const created = await api.scenePromptTemplatesCreate(projectId, {
        name: name.trim(),
        promptText: workingText,
        generatorFamily: generatorFamily || "",
        generatorId: generatorId || "",
        sourceSceneId: sourceSceneId || "",
      });
      setSelectedId(created.id);
    });
  };

  const onUpdate = () => {
    if (!selectedId) return;
    setMenuOpen(false);
    const ok = window.confirm(
      `Overwrite template "${selected?.name || selectedId}" with current Timed Prompt text?`,
    );
    if (!ok) return;
    void run("Updated", async () => {
      await api.scenePromptTemplatesUpdate(projectId, selectedId, {
        promptText: workingText,
        generatorFamily: generatorFamily || undefined,
        generatorId: generatorId || undefined,
        sourceSceneId: sourceSceneId || undefined,
      });
    });
  };

  const onRename = () => {
    if (!selectedId) return;
    setMenuOpen(false);
    const name = window.prompt("Rename template", selected?.name || "");
    if (!name || !name.trim()) return;
    void run("Renamed", async () => {
      await api.scenePromptTemplatesRename(projectId, selectedId, name.trim());
    });
  };

  const onDelete = () => {
    if (!selectedId) return;
    setMenuOpen(false);
    const ok = window.confirm(
      `Delete template "${selected?.name || selectedId}"? This cannot be undone.`,
    );
    if (!ok) return;
    void run("Deleted", async () => {
      await api.scenePromptTemplatesDelete(projectId, selectedId);
      setSelectedId("");
    });
  };

  return (
    <div className="scene-prompt-template-bar" data-testid={`${testIdPrefix}-bar`}>
      <label className="field">
        <span>Scene Prompt Templates</span>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
          <select
            data-testid={`${testIdPrefix}-select`}
            value={selectedId}
            disabled={busy}
            onChange={(e) => setSelectedId(e.target.value)}
            style={{ flex: "1 1 160px", minWidth: 140 }}
          >
            <option value="">Select template…</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.promptTextLength ?? (t.promptText || "").length})
              </option>
            ))}
          </select>
          <button type="button" data-testid={`${testIdPrefix}-load`} disabled={busy || !selectedId} onClick={() => void onLoad()}>
            Load
          </button>
          <button type="button" data-testid={`${testIdPrefix}-save`} disabled={busy} onClick={onSave}>
            Save Current Prompt as Template
          </button>
          <div className="overflow-wrap" ref={menuRef}>
            <button
              type="button"
              data-testid={`${testIdPrefix}-overflow`}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              aria-label="Template actions"
              disabled={busy || !selectedId}
              onClick={() => setMenuOpen((v) => !v)}
            >
              ⋯
            </button>
            {menuOpen ? (
              <div className="overflow-menu" role="menu" data-testid={`${testIdPrefix}-overflow-menu`}>
                <button
                  type="button"
                  role="menuitem"
                  data-testid={`${testIdPrefix}-update`}
                  disabled={busy || !selectedId}
                  onClick={onUpdate}
                >
                  Update
                </button>
                <button
                  type="button"
                  role="menuitem"
                  data-testid={`${testIdPrefix}-rename`}
                  disabled={busy || !selectedId}
                  onClick={onRename}
                >
                  Rename
                </button>
                <button
                  type="button"
                  role="menuitem"
                  className="danger"
                  data-testid={`${testIdPrefix}-delete`}
                  disabled={busy || !selectedId}
                  onClick={onDelete}
                >
                  Delete
                </button>
              </div>
            ) : null}
          </div>
        </div>
        <p className="scene-meta" data-testid={`${testIdPrefix}-hint`}>
          Named Timed Prompt snapshots (server). Load copies exact text into the working copy. Library entry stays independent.
        </p>
        {status ? (
          <p className="scene-meta" data-testid={`${testIdPrefix}-status`}>
            {status}
          </p>
        ) : null}
        {error ? (
          <p className="scene-meta" data-testid={`${testIdPrefix}-error`}>
            {error}
          </p>
        ) : null}
      </label>
    </div>
  );
}
