import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import type { Project } from "../types";
import { LearningPanel } from "./LearningPanel";
import { LearningEvolutionPanel } from "./LearningEvolutionPanel";
import { CoDirectorMemoryPanel } from "./CoDirectorMemoryPanel";
import { LanguageSettings } from "../i18n";
import { ASPECT_PRESETS, FPS_OPTIONS } from "../workspacePrefs";
import { PRIMARY_PROJECT_TYPES } from "../projectTypes";
import { HostedProvidersPanel } from "./HostedProvidersPanel";

const TABS = [
  ["general", "general"],
  ["language", "languageTab"],
  ["learning", "learning"],
  ["defaults", "defaults"],
  ["library", "library"],
  ["integrations", "integrations"],
  ["rendering", "rendering"],
  ["collab", "collab"],
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
  const { t } = useTranslation(["settings", "common", "navigation"]);
  const [tab, setTab] = useState<TabId>("general");
  const [defaults, setDefaults] = useState<Record<string, unknown>>(() => parseDefaults(project.defaults_json));
  const [typeSlug, setTypeSlug] = useState(project.primary_project_type || "custom");
  const [typePreview, setTypePreview] = useState<any>(null);
  const [typeBusy, setTypeBusy] = useState(false);
  const [customSlug, setCustomSlug] = useState("");

  useEffect(() => {
    const forced = sessionStorage.getItem("adept_settings_tab") as TabId | null;
    if (forced && TABS.some(([id]) => id === forced)) {
      setTab(forced);
      sessionStorage.removeItem("adept_settings_tab");
    }
  }, []);

  useEffect(() => {
    setDefaults(parseDefaults(project.defaults_json));
    setTypeSlug(project.primary_project_type || "custom");
  }, [project.defaults_json, project.primary_project_type]);

  const saveMeta = (patch: Partial<Project>) => api.updateProject(project.id, patch).then(onChange);

  const saveDefaults = async (next: Record<string, unknown>) => {
    setDefaults(next);
    await api.updateProject(project.id, { defaults_json: JSON.stringify(next) } as any);
    onChange();
  };

  return (
    <div className="page project-settings">
      <h1>{t("settings:title")}</h1>
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
            {t(`settings:${label}`)}
          </button>
        ))}
      </div>

      {tab === "language" && (
        <div className="settings-panel">
          <LanguageSettings project={project} onProjectChange={onChange} />
        </div>
      )}

      {tab === "general" && (
        <div className="settings-panel">
          <div className="field">
            <label>{t("settings:name")}</label>
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
          <div className="field" data-testid="project-type-settings">
            <label>Project type</label>
            <p className="muted">
              Active: <strong>{project.primary_project_type || "custom"}</strong>
              {project.project_traits_json ? ` · traits ${project.project_traits_json}` : ""}
            </p>
            <select
              value={typeSlug}
              onChange={(e) => {
                setTypeSlug(e.target.value);
                setTypePreview(null);
              }}
              data-testid="project-type-select"
            >
              {PRIMARY_PROJECT_TYPES.map((t) => (
                <option key={t.slug} value={t.slug}>
                  {t.displayName}
                </option>
              ))}
            </select>
            <div className="row" style={{ marginTop: "0.5rem", gap: "0.5rem" }}>
              <button
                type="button"
                className="ghost"
                disabled={typeBusy || typeSlug === (project.primary_project_type || "custom")}
                onClick={async () => {
                  setTypeBusy(true);
                  try {
                    setTypePreview(
                      await api.previewProjectTypeChange(project.id, { primaryProjectType: typeSlug })
                    );
                  } catch {
                    setTypePreview({ error: "Preview unavailable (enable STUDIO_FEATURE_TEMPLATES_PRESETS_V1)." });
                  } finally {
                    setTypeBusy(false);
                  }
                }}
              >
                Preview type change
              </button>
              <button
                type="button"
                className="primary"
                disabled={typeBusy || !typePreview || typePreview.error || !typePreview.allowed}
                data-testid="apply-project-type"
                onClick={async () => {
                  setTypeBusy(true);
                  try {
                    await api.applyProjectTypeChange(project.id, {
                      primaryProjectType: typeSlug,
                      applyDimensionDefaults: true,
                    });
                    setTypePreview(null);
                    onChange();
                  } finally {
                    setTypeBusy(false);
                  }
                }}
              >
                Apply non-destructive change
              </button>
            </div>
            {typePreview && (
              <pre className="muted" style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>
                {JSON.stringify(typePreview.deltas || typePreview, null, 2)}
              </pre>
            )}
            <div className="row" style={{ marginTop: "0.75rem", gap: "0.5rem" }}>
              <input
                placeholder="custom-type-slug"
                value={customSlug}
                onChange={(e) => setCustomSlug(e.target.value)}
                aria-label="Custom project type slug"
              />
              <button
                type="button"
                className="ghost"
                disabled={typeBusy || !customSlug.trim()}
                onClick={async () => {
                  setTypeBusy(true);
                  try {
                    await api.saveCustomProjectType({
                      projectId: project.id,
                      slug: customSlug.trim(),
                    });
                    onChange();
                  } finally {
                    setTypeBusy(false);
                  }
                }}
              >
                Save as custom project type
              </button>
            </div>
          </div>
        </div>
      )}

      {tab === "learning" && (
        <>
          <LearningPanel project={project} onChange={onChange} />
          <CoDirectorMemoryPanel project={project} />
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
                  {e === "ltx" ? "LTX 2.5" : e === "wan" ? "WAN 2.2" : e === "fal_seedance" ? "Seedance" : e === "fal_kling" ? "Kling" : e === "fal_veo" ? "Veo" : e === "fal_runway" ? "Runway" : e}
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
                {(
                  [
                    ["auto", "auto (Qwen-Image-2512 recommended)"],
                    ["qwen2512", "Qwen-Image-2512 (Recommended)"],
                    ["flux", "FLUX (Alternative)"],
                    ["zimage", "Z-Image (Fallback)"],
                    ["hidream", "hidream"],
                    ["sd35", "sd35"],
                    ["custom", "custom"],
                  ] as const
                ).map(([m, label]) => (
                  <option key={m} value={m}>
                    {label}
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

      {tab === "integrations" && <HostedProvidersPanel />}

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
