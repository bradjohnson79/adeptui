import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Project } from "../types";
import {
  buildPromptsFromSheet,
  emptyMasterSheet,
  validateSheet,
  type IngredientKind,
  type IngredientPriority,
  type MasterSheetIngredient,
  type SceneMasterSheet,
} from "../mastersheet/types";

const KINDS: IngredientKind[] = [
  "character",
  "wardrobe",
  "prop",
  "environment",
  "camera",
  "lighting",
  "color_mood",
  "action",
  "style",
];

const PRIOS: IngredientPriority[] = ["Required", "Preferred", "Optional", "Background", "Exclude"];

/**
 * Scene Master Sheet workspace.
 * Master Sheet = what exists; Spatial = where; Storyboard = how framed; Director = assembled.
 * Ingredients Render is an OUTPUT of structured data — never a collage prompt.
 */
export function SceneMasterSheetWorkspace({
  project,
  sceneId,
  onChange,
  onGoSpatial,
}: {
  project: Project;
  sceneId?: string;
  onChange?: () => Promise<void>;
  onGoSpatial?: () => void;
}) {
  const scene = project.scenes.find((s) => s.id === sceneId) || project.scenes[0];
  const [sheet, setSheet] = useState<SceneMasterSheet | null>(null);
  const [view, setView] = useState<"structured" | "visual" | "split">("split");
  const [busy, setBusy] = useState(false);
  const [issues, setIssues] = useState<{ level: string; text: string }[]>([]);
  const [sel, setSel] = useState<string | null>(null);

  const load = async () => {
    if (!scene) return;
    try {
      const s = await api.getMasterSheet(project.id, scene.id);
      setSheet(s);
    } catch {
      const boot = emptyMasterSheet(project.id, scene.id, `${scene.name} Master Sheet`);
      if (scene.prompt) boot.prompt = scene.prompt;
      setSheet(boot);
    }
  };

  useEffect(() => {
    load().catch(console.error);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id, scene?.id]);

  const selected = useMemo(
    () => sheet?.ingredients.find((i) => i.id === sel) || null,
    [sheet, sel]
  );

  const save = async (next: SceneMasterSheet) => {
    setBusy(true);
    try {
      const prompts = buildPromptsFromSheet(next);
      const payload = { ...next, prompt: next.prompt || prompts.prompt, negative_prompt: next.negative_prompt || prompts.negative_prompt };
      const saved = await api.putMasterSheet(project.id, scene!.id, payload);
      setSheet(saved);
      await onChange?.();
    } finally {
      setBusy(false);
    }
  };

  const addIngredient = (kind: IngredientKind) => {
    if (!sheet) return;
    const ing: MasterSheetIngredient = {
      id: `ing-${Date.now()}`,
      kind,
      label: kind === "character" ? "Character" : kind.replace("_", " "),
      priority: kind === "character" || kind === "environment" ? "Required" : "Preferred",
      description: "",
    };
    const next = { ...sheet, ingredients: [...sheet.ingredients, ing], updated_at: new Date().toISOString() };
    setSheet(next);
    setSel(ing.id);
  };

  const updateSelected = (patch: Partial<MasterSheetIngredient>) => {
    if (!sheet || !sel) return;
    const next = {
      ...sheet,
      ingredients: sheet.ingredients.map((i) => (i.id === sel ? { ...i, ...patch } : i)),
    };
    setSheet(next);
  };

  const autoPrompt = () => {
    if (!sheet) return;
    const { prompt, negative_prompt } = buildPromptsFromSheet({ ...sheet, prompt: "", negative_prompt: "" });
    setSheet({ ...sheet, prompt, negative_prompt });
  };

  if (!scene) {
    return (
      <div className="page">
        <p className="empty">Add a scene first to create a Master Sheet.</p>
      </div>
    );
  }

  if (!sheet) {
    return (
      <div className="page">
        <p className="empty">Loading Master Sheet…</p>
      </div>
    );
  }

  const board = (
    <div className="ingredients-board" aria-label="Visual ingredients board">
      {sheet.ingredients.length === 0 && (
        <p className="muted" style={{ gridColumn: "1 / -1" }}>
          Add characters (large), wardrobe, environment, camera, lighting… This board is structured data — not a collage.
        </p>
      )}
      {sheet.ingredients.map((ing) => (
        <button
          key={ing.id}
          type="button"
          className={`ingredient-tile ${ing.kind === "character" ? "character" : ""}`}
          onClick={() => setSel(ing.id)}
          aria-pressed={sel === ing.id}
        >
          <div className="pri">
            {ing.priority} · {ing.kind}
            {ing.uncertain ? " · uncertain" : ""}
          </div>
          <strong>{ing.label}</strong>
          <p className="scene-meta">{ing.description || "—"}</p>
        </button>
      ))}
    </div>
  );

  return (
    <div className="master-sheet-workspace">
      <header className="row" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem" }}>
        <div>
          <p className="eyebrow">Whole-Scene Package</p>
          <h1 className="section-heading" style={{ margin: 0 }}>
            {sheet.title}
          </h1>
          <p className="muted">
            Scene: {scene.name} · {sheet.version} · state {sheet.state_id}
            {sheet.approved_authority ? " · Scene Authority ✓" : ""}
          </p>
        </div>
        <div className="master-sheet-tabs" role="tablist">
          {(["structured", "visual", "split"] as const).map((v) => (
            <button key={v} type="button" role="tab" className={view === v ? "primary" : ""} onClick={() => setView(v)}>
              {v === "structured" ? "Structured" : v === "visual" ? "Visual Sheet" : "Split"}
            </button>
          ))}
        </div>
      </header>

      <div className="master-sheet-tools">
        {KINDS.slice(0, 6).map((k) => (
          <button key={k} type="button" onClick={() => addIngredient(k)}>
            + {k}
          </button>
        ))}
        <button type="button" onClick={autoPrompt}>
          Build Prompt
        </button>
        <button
          type="button"
          onClick={async () => {
            const local = validateSheet(sheet);
            try {
              const remote = await api.validateMasterSheet(project.id, scene.id);
              setIssues([...(remote.issues || []), ...local]);
            } catch {
              setIssues(local);
            }
          }}
        >
          Validate
        </button>
        <button type="button" className="primary" disabled={busy} onClick={() => void save(sheet)}>
          {busy ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          onClick={async () => {
            await api.setMasterSheetAuthority(project.id, scene.id, !sheet.approved_authority);
            await load();
          }}
        >
          {sheet.approved_authority ? "Clear Authority" : "Set Scene Authority"}
        </button>
        <button type="button" onClick={() => onGoSpatial?.()}>
          Spatial
        </button>
        <button type="button" disabled title="Export image stub">
          Export
        </button>
        <button type="button" disabled title="Generate stub">
          Generate
        </button>
      </div>

      {issues.length > 0 && (
        <ul className="health-list" style={{ margin: "0.75rem 0" }}>
          {issues.map((i, idx) => (
            <li key={idx}>
              <span className={`status-badge ${i.level === "bad" ? "bad" : "warn"}`}>{i.level}</span> {i.text}
            </li>
          ))}
        </ul>
      )}

      <div className={view === "split" ? "master-sheet-layout" : ""} style={{ marginTop: "0.75rem" }}>
        {(view === "visual" || view === "split") && board}
        {(view === "structured" || view === "split") && (
          <aside className="dash-card" style={{ padding: "1rem" }}>
            <h2 style={{ marginTop: 0, fontSize: "1.1rem" }}>Inspector</h2>
            {!selected ? (
              <p className="muted">Select an ingredient or edit prompts below.</p>
            ) : (
              <>
                <label className="field">
                  Label
                  <input value={selected.label} onChange={(e) => updateSelected({ label: e.target.value })} />
                </label>
                <label className="field">
                  Kind
                  <select
                    value={selected.kind}
                    onChange={(e) => updateSelected({ kind: e.target.value as IngredientKind })}
                  >
                    {KINDS.map((k) => (
                      <option key={k} value={k}>
                        {k}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  Priority
                  <select
                    value={selected.priority}
                    onChange={(e) => updateSelected({ priority: e.target.value as IngredientPriority })}
                  >
                    {PRIOS.map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  Description
                  <textarea
                    rows={3}
                    value={selected.description || ""}
                    onChange={(e) => updateSelected({ description: e.target.value })}
                  />
                </label>
              </>
            )}
            <label className="field" style={{ marginTop: "0.75rem" }}>
              Prompt (final scene — no collage language)
              <textarea rows={4} value={sheet.prompt} onChange={(e) => setSheet({ ...sheet, prompt: e.target.value })} />
            </label>
            <label className="field">
              Negative prompt
              <textarea
                rows={3}
                value={sheet.negative_prompt}
                onChange={(e) => setSheet({ ...sheet, negative_prompt: e.target.value })}
              />
            </label>
          </aside>
        )}
      </div>
    </div>
  );
}
