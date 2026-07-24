import { useEffect, useState } from "react";
import type { Project } from "../types";
import { api } from "../api";
import { PanelHeading } from "./HelpTip";

const CATEGORIES = [
  ["prompts", "Learn my preferred prompts"],
  ["camera", "Learn my camera style"],
  ["pacing", "Learn my pacing"],
  ["engines", "Learn my engine choices"],
  ["continuity", "Learn my continuity preferences"],
  ["render", "Learn my render preferences"],
  ["dialogue", "Learn my dialogue style"],
  ["motion", "Learn my motion preferences"],
  ["genre", "Learn my genre / style"],
  ["profiles", "Learn my profile usage"],
  ["storyboard", "Learn my storyboard style"],
  ["spatial", "Learn my spatial staging"],
  ["coverage", "Learn my camera coverage"],
  ["script_structure", "Learn my script structure"],
] as const;

type LearningState = {
  enabled: Record<string, boolean>;
  items: { id: string; category: string; text: string; enabled: boolean }[];
  dismissed_continuity: string[];
};

export function LearningPanel({ project, onChange }: { project: Project; onChange: () => void }) {
  const [state, setState] = useState<LearningState | null>(null);
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [newText, setNewText] = useState("");
  const [newCat, setNewCat] = useState("prompts");

  const refresh = async () => {
    const s = await api.getLearning(project.id);
    setState(s);
    const c = await api.continuitySuggestions(project.id);
    setSuggestions(c.suggestions || []);
  };

  useEffect(() => {
    refresh().catch(console.error);
  }, [project.id]);

  if (!state) return null;

  const save = async (next: LearningState) => {
    setState(next);
    await api.putLearning(project.id, next);
    onChange();
  };

  return (
    <div className="panel">
      <PanelHeading
        title="AI Learning"
        tip="Project-aware creative preferences — never hidden. Toggle categories and edit What I've Learned."
      />
      <div className="continuity-grid">
        {CATEGORIES.map(([id, label]) => (
          <label key={id} className="continuity-row">
            <span>{label}</span>
            <input
              type="checkbox"
              checked={!!state.enabled[id]}
              style={{ width: "auto" }}
              onChange={(e) =>
                save({ ...state, enabled: { ...state.enabled, [id]: e.target.checked } })
              }
            />
          </label>
        ))}
      </div>
      <div className="row-actions" style={{ marginTop: 10 }}>
        <button
          type="button"
          onClick={async () => {
            await api.resetLearning(project.id);
            refresh();
          }}
        >
          Reset Project Learning
        </button>
        <button
          type="button"
          onClick={async () => {
            const data = await api.exportLearning(project.id);
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `learning-${project.id.slice(0, 8)}.json`;
            a.click();
            URL.revokeObjectURL(url);
          }}
        >
          Export Learning
        </button>
        <label className="ghost" style={{ cursor: "pointer" }}>
          Import Learning
          <input
            type="file"
            accept="application/json"
            hidden
            onChange={async (e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              const text = await f.text();
              await api.importLearning(project.id, JSON.parse(text));
              refresh();
            }}
          />
        </label>
      </div>

      <div className="section-label" style={{ marginTop: 12 }}>
        What I've Learned
      </div>
      {state.items.length === 0 && <p className="scene-meta">No learned preferences yet.</p>}
      <ul className="learning-list">
        {state.items.map((item) => (
          <li key={item.id}>
            <label style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
              <input
                type="checkbox"
                checked={item.enabled}
                style={{ width: "auto", marginTop: 4 }}
                onChange={(e) =>
                  save({
                    ...state,
                    items: state.items.map((it) =>
                      it.id === item.id ? { ...it, enabled: e.target.checked } : it
                    ),
                  })
                }
              />
              <span>
                <span className="pill">{item.category}</span> {item.text}
              </span>
            </label>
            <button
              type="button"
              className="ghost"
              onClick={() => save({ ...state, items: state.items.filter((it) => it.id !== item.id) })}
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
      <div className="row-actions">
        <select value={newCat} onChange={(e) => setNewCat(e.target.value)} style={{ width: 140 }}>
          {CATEGORIES.map(([id]) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
        <input
          value={newText}
          onChange={(e) => setNewText(e.target.value)}
          placeholder="Add an approved preference…"
        />
        <button
          type="button"
          onClick={() => {
            if (!newText.trim()) return;
            save({
              ...state,
              items: [
                ...state.items,
                {
                  id: Math.random().toString(36).slice(2, 10),
                  category: newCat,
                  text: newText.trim(),
                  enabled: true,
                },
              ],
            });
            setNewText("");
          }}
        >
          Add
        </button>
      </div>

      <div className="section-label" style={{ marginTop: 14 }}>
        Continuity suggestions
      </div>
      {suggestions.length === 0 && <p className="scene-meta">No suggestions right now.</p>}
      {suggestions.map((s) => (
        <div key={s.id} className="recommend-card">
          <p className="scene-meta">{s.message}</p>
          <button
            type="button"
            onClick={async () => {
              await api.dismissContinuity(project.id, s.id);
              refresh();
            }}
          >
            Dismiss
          </button>
        </div>
      ))}
    </div>
  );
}
