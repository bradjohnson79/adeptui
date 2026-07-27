import { useEffect, useState } from "react";
import { api } from "../api";
import type { Project } from "../types";
import { LearningPanel } from "./LearningPanel";
import { LearningEvolutionPanel } from "./LearningEvolutionPanel";
import { ASPECT_PRESETS, FPS_OPTIONS } from "../workspacePrefs";

const TABS = [
  ["general", "General"],
  ["learning", "AI Learning"],
  ["defaults", "Defaults"],
  ["library", "Library"],
  ["integrations", "Integrations"],
  ["rendering", "Rendering"],
  ["collab", "Collaboration"],
] as const;

type TabId = (typeof TABS)[number][0];

function parseDefaults(raw?: string) {
  try {
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

export function ProjectSettings({ project, onChange }: { project: Project; onChange: () => void }) {
  const [tab, setTab] = useState<TabId>("general");
  const [defaults, setDefaults] = useState<Record<string, unknown>>(() => parseDefaults(project.defaults_json));
  const [falStatus, setFalStatus] = useState<{ configured: boolean; hint?: string | null } | null>(null);
  const [falKey, setFalKey] = useState("");

  useEffect(() => {
    const forced = sessionStorage.getItem("adept_settings_tab") as TabId | null;
    if (forced && TABS.some(([id]) => id === forced)) {
      setTab(forced);
      sessionStorage.removeItem("adept_settings_tab");
    }
  }, []);

  useEffect(() => {
    setDefaults(parseDefaults(project.defaults_json));
  }, [project.defaults_json]);

  useEffect(() => {
    if (tab === "integrations") api.falKeyStatus().then(setFalStatus).catch(() => setFalStatus(null));
  }, [tab]);

  const saveMeta = (patch: Partial<Project>) => api.updateProject(project.id, patch).then(onChange);

  const saveDefaults = async (next: Record<string, unknown>) => {
    setDefaults(next);
    await api.updateProject(project.id, { defaults_json: JSON.stringify(next) } as any);
    onChange();
  };

  return (
    <div className="page project-settings">
      <h1>Project Settings</h1>
      <div className="workspace-tabs" role="tablist">
        {TABS.map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={tab === id ? "primary" : ""}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "general" && (
        <div className="settings-panel">
          <div className="field">
            <label>Name</label>
            <input value={project.name} onChange={(e) => saveMeta({ name: e.target.value })} />
          </div>
          <div className="field">
            <label>Description</label>
            <textarea
              value={project.description || ""}
              onChange={(e) => saveMeta({ description: e.target.value } as any)}
            />
          </div>
          <div className="field">
            <label>Company</label>
            <input
              value={project.company || ""}
              onChange={(e) => saveMeta({ company: e.target.value } as any)}
            />
          </div>
          <div className="field">
            <label>Director</label>
            <input
              value={project.director_name || ""}
              onChange={(e) => saveMeta({ director_name: e.target.value } as any)}
            />
          </div>
          <div className="field">
            <label>Version</label>
            <input
              value={project.version || "1.0"}
              onChange={(e) => saveMeta({ version: e.target.value } as any)}
            />
          </div>
          <div className="field">
            <label>Tags (JSON array)</label>
            <input
              value={project.tags_json || "[]"}
              onChange={(e) => saveMeta({ tags_json: e.target.value } as any)}
            />
          </div>
        </div>
      )}

      {tab === "learning" && (
        <>
          <LearningPanel project={project} onChange={onChange} />
          <LearningEvolutionPanel project={project} enabled />
        </>
      )}

      {tab === "defaults" && (
        <div className="settings-panel">
          <p className="muted">Seeds new Txt2Vid / ImageGen / Director scenes.</p>
          <div className="field">
            <label>Default engine</label>
            <select
              value={String(defaults.engine || project.engine_default)}
              onChange={(e) => saveDefaults({ ...defaults, engine: e.target.value })}
            >
              {["auto", "ltx", "wan", "fal_seedance", "fal_kling", "fal_veo", "fal_runway"].map((e) => (
                <option key={e} value={e}>
                  {e}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Aspect</label>
            <select
              value={String(defaults.aspect || "16:9")}
              onChange={(e) => saveDefaults({ ...defaults, aspect: e.target.value })}
            >
              {ASPECT_PRESETS.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>FPS</label>
            <select
              value={String(defaults.fps ?? "auto")}
              onChange={(e) =>
                saveDefaults({
                  ...defaults,
                  fps: e.target.value === "auto" ? "auto" : Number(e.target.value),
                })
              }
            >
              {FPS_OPTIONS.map((f) => (
                <option key={String(f)} value={String(f)}>
                  {f}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Resolution label</label>
            <select
              value={String(defaults.resolution || "720p")}
              onChange={(e) => saveDefaults({ ...defaults, resolution: e.target.value })}
            >
              {["720p", "1080p", "1440p", "4K"].map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Prompt style</label>
            <input
              value={String(defaults.prompt_style || "")}
              onChange={(e) => saveDefaults({ ...defaults, prompt_style: e.target.value })}
            />
          </div>
            <div className="field">
              <label>ImageGen model preference</label>
              <select
                value={String(defaults.imagegen_model || "auto")}
                onChange={(e) => saveDefaults({ ...defaults, imagegen_model: e.target.value })}
              >
                {["auto", "flux", "hidream", "sd35", "custom"].map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Storyboard style</label>
              <select
                value={String(defaults.storyboard_style || "Pencil storyboard")}
                onChange={(e) => saveDefaults({ ...defaults, storyboard_style: e.target.value })}
              >
                {[
                  "Pencil storyboard",
                  "Ink storyboard",
                  "Grayscale cinematic",
                  "Color concept frame",
                  "Anime storyboard",
                  "Photoreal previs",
                  "Production still",
                ].map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Spatial guidance</label>
              <select
                value={String(defaults.spatial_guidance || "balanced")}
                onChange={(e) => saveDefaults({ ...defaults, spatial_guidance: e.target.value })}
              >
                {["loose", "balanced", "strict"].map((g) => (
                  <option key={g} value={g}>
                    {g}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

      {tab === "library" && (
        <div className="settings-panel">
          <p>Project library is scoped per project; promote assets to Global from the Library workspace.</p>
          <p className="muted">Shared scope uses shared_project_ids_json on assets (Phase 5).</p>
        </div>
      )}

      {tab === "integrations" && (
        <div className="settings-panel">
          <h3>fal.ai</h3>
          <p className="muted">
            {falStatus?.configured ? `Configured ${falStatus.hint || ""}` : "Not configured — required for Txt2Vid / fal engines."}
          </p>
          <div className="field">
            <label>API key</label>
            <input type="password" value={falKey} onChange={(e) => setFalKey(e.target.value)} />
          </div>
          <div className="row">
            <button
              type="button"
              className="primary"
              onClick={() => api.falKeySet(falKey).then(setFalStatus).then(() => setFalKey(""))}
            >
              Save key
            </button>
            <button type="button" onClick={() => api.falKeyClear().then(setFalStatus)}>
              Clear
            </button>
          </div>
        </div>
      )}

      {tab === "rendering" && (
        <div className="settings-panel">
          <div className="field">
            <label>VRAM tier (GB)</label>
            <input
              type="number"
              value={project.vram_gb}
              onChange={(e) =>
                api.updateProject(project.id, { vram_gb: Number(e.target.value), apply_vram_profile: true }).then(onChange)
              }
            />
          </div>
          <div className="field">
            <label>Preset</label>
            <select
              value={project.preset}
              onChange={(e) => api.updateProject(project.id, { preset: e.target.value as any }).then(onChange)}
            >
              <option value="draft">draft</option>
              <option value="quality">quality</option>
            </select>
          </div>
        </div>
      )}

      {tab === "collab" && (
        <div className="settings-panel">
          <p className="muted">Multi-user collaboration is a placeholder in this release.</p>
        </div>
      )}
    </div>
  );
}
