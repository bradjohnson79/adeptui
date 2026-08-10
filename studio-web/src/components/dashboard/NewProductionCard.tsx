import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { PROJECT_TEMPLATES } from "../../dashboardImages";
import { apiUrl } from "../../runtime/apiBase";
import {
  PRIMARY_PROJECT_TYPES,
  resolveCreateType,
  type PrimaryProjectType,
} from "../../projectTypes";
// Load video generators dynamically to avoid type issues with the large api module
async function loadVideoGenerators(): Promise<Array<{ id: string; label: string; available: boolean }>> {
  try {
    const res = await fetch(apiUrl("/api/knowledge-cards/video-generators"));
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export type NewProductionOpts = {
  name: string;
  primaryProjectType: string;
  projectTraits: string[];
  aspect?: string;
  resolution?: string;
  fps?: number | "auto";
  storyboard_style?: string;
  preferred_video_generator?: string;
};

const STORYBOARD_STYLES = [
  { id: "pencil", label: "Pencil Storyboard" },
  { id: "low_poly_3d", label: "Low Poly 3D Storyboard" },
  { id: "image", label: "Image Storyboard" },
];

interface VideoGeneratorOption {
  id: string;
  label: string;
  available: boolean;
}

function scrollExpandedIntoView(node: HTMLElement | null) {
  if (!node) return;
  window.requestAnimationFrame(() => {
    node.scrollIntoView({ block: "nearest", behavior: "smooth" });
  });
}

export function NewProductionCard({
  busy,
  onCreate,
  templatesEnabled = true,
  initialName,
  onCancel,
  onSelectTemplate,
  error,
}: {
  busy: boolean;
  onCreate: (opts: NewProductionOpts) => void;
  /** When false, falls back to a simpler primary-only list still using slugs. */
  templatesEnabled?: boolean;
  initialName?: string;
  onCancel?: () => void;
  onSelectTemplate?: (templateId: string) => void;
  error?: string | null;
}) {
  const defaultName = initialName?.trim() || "Untitled Project";
  const [name, setName] = useState(defaultName);
  const [primary, setPrimary] = useState<PrimaryProjectType>(
    PRIMARY_PROJECT_TYPES.find((t) => t.slug === "short_film") || PRIMARY_PROJECT_TYPES[0]
  );
  const [subtype, setSubtype] = useState<string>("");
  const [traits, setTraits] = useState<string[]>([]);
  const [optionalOpen, setOptionalOpen] = useState(false);
  const [templatesOpen, setTemplatesOpen] = useState(false);
  const [aspect, setAspect] = useState("16:9");
  const [resolution, setResolution] = useState("1080p");
  const [fps, setFps] = useState<string>("auto");
  const [style, setStyle] = useState("pencil");
  const [videoGens, setVideoGens] = useState<VideoGeneratorOption[]>([]);
  const [preferredGen, setPreferredGen] = useState("automatic");
  const optionalPanelRef = useRef<HTMLDivElement>(null);

  // Fetch available video generators on mount
  useEffect(() => {
    loadVideoGenerators().then(setVideoGens);
  }, []);
  const templatesPanelRef = useRef<HTMLDivElement>(null);

  const previewType = useMemo(
    () => resolveCreateType(primary.slug, subtype || null),
    [primary.slug, subtype]
  );
  const previewLabel = useMemo(() => {
    if (!subtype) return primary.displayName;
    return primary.subtypes?.find((entry) => entry.slug === subtype)?.displayName || subtype.replace(/_/g, " ");
  }, [primary, subtype]);
  const trimmedName = name.trim();
  const nameError = trimmedName ? null : "Give your project a name before creating it.";
  const canSubmit = !busy && !nameError;
  const resolvedFps = fps === "auto" ? 24 : Number(fps);

  const toggleTrait = (trait: string) => {
    setTraits((prev) => (prev.includes(trait) ? prev.filter((t) => t !== trait) : [...prev, trait]));
  };

  useEffect(() => {
    setName(defaultName);
  }, [defaultName]);

  useEffect(() => {
    if (optionalOpen) scrollExpandedIntoView(optionalPanelRef.current);
  }, [optionalOpen]);

  useEffect(() => {
    if (templatesOpen) scrollExpandedIntoView(templatesPanelRef.current);
  }, [templatesOpen]);

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (!canSubmit) return;
    onCreate({
      name: trimmedName,
      primaryProjectType: previewType,
      projectTraits: traits,
      aspect,
      resolution,
      fps: resolvedFps,
      storyboard_style: style,
      preferred_video_generator: preferredGen,
    });
  };

  return (
    <section className="dash-card new-production-card" id="new-production">
      <form className="new-production-card__form" onSubmit={submit}>
        <div
          className="new-production-card__body"
          data-testid="create-project-modal-body"
          tabIndex={0}
          aria-label="Create project details"
        >
          <p className="eyebrow">New production</p>
          <h2>Start with a project type</h2>
          <p className="muted">
            Name it now, then open Setup, your library, or Co-Director when you are ready to keep building.
          </p>
          <div className="field">
            <label htmlFor="np-name">Project name</label>
            <input
              id="np-name"
              value={name}
              aria-invalid={nameError ? "true" : "false"}
              onChange={(e) => setName(e.target.value)}
            />
            {nameError ? (
              <p className="new-production-card__field-error" role="alert">
                {nameError}
              </p>
            ) : null}
          </div>
          <div className="field">
            <label>Project type</label>
            <div className="type-chips" role="listbox" aria-label="Primary project type">
              {PRIMARY_PROJECT_TYPES.map((t) => (
                <button
                  key={t.slug}
                  type="button"
                  role="option"
                  aria-selected={primary.slug === t.slug}
                  className={primary.slug === t.slug ? "primary" : ""}
                  data-testid={`project-type-${t.slug}`}
                  onClick={() => {
                    setPrimary(t);
                    setSubtype("");
                    setTraits([]);
                    if (t.slug === "social_media") setAspect("9:16");
                    else if (t.slug === "feature_film") setAspect("2.39:1");
                    else setAspect("16:9");
                  }}
                >
                  {t.displayName}
                </button>
              ))}
            </div>
          </div>
          {templatesEnabled && primary.subtypes && primary.subtypes.length > 0 && (
            <div className="field" data-testid="create-project-refine-type">
              <label>Refine type</label>
              <div className="type-chips" role="listbox" aria-label="Project subtype">
                <button
                  type="button"
                  role="option"
                  aria-selected={!subtype}
                  className={!subtype ? "primary" : ""}
                  onClick={() => setSubtype("")}
                >
                  {primary.displayName} (default)
                </button>
                {primary.subtypes.map((s) => (
                  <button
                    key={s.slug}
                    type="button"
                    role="option"
                    aria-selected={subtype === s.slug}
                    className={subtype === s.slug ? "primary" : ""}
                    data-testid={`project-subtype-${s.slug}`}
                    onClick={() => setSubtype(s.slug)}
                  >
                    {s.displayName}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="new-production-card__summary" data-testid="project-type-preview">
            <p className="new-production-card__summary-label">Profile summary</p>
            <p className="new-production-card__summary-copy">
              <strong>{previewLabel}</strong>
              {traits.length ? ` · traits: ${traits.map((trait) => trait.replace(/_/g, " ")).join(", ")}` : ""}
              {` · ${aspect} · ${resolution} · ${resolvedFps} fps`}
            </p>
          </div>
          <div className="new-production-card__optional">
            <div className="new-production-card__optional-actions">
              <button
                type="button"
                className="ghost"
                aria-expanded={optionalOpen}
                aria-controls="create-project-optional-panel"
                data-testid="create-project-optional-toggle"
                onClick={() => {
                  setOptionalOpen((v) => {
                    const next = !v;
                    if (next) setTemplatesOpen(false);
                    return next;
                  });
                }}
              >
                {optionalOpen ? "Hide optional settings" : "Optional settings"}
              </button>
              {onSelectTemplate ? (
                <button
                  type="button"
                  className="ghost new-production-card__browse-link"
                  aria-expanded={templatesOpen}
                  aria-controls="create-project-templates-panel"
                  data-testid="create-project-templates-toggle"
                  onClick={() => {
                    setTemplatesOpen((v) => {
                      const next = !v;
                      if (next) setOptionalOpen(false);
                      return next;
                    });
                  }}
                  disabled={busy}
                >
                  {templatesOpen ? "Hide templates" : "Browse templates instead"}
                </button>
              ) : null}
            </div>
            {optionalOpen && (
              <div
                ref={optionalPanelRef}
                id="create-project-optional-panel"
                className="new-production-card__optional-panel"
                data-testid="create-project-optional-panel"
              >
                {templatesEnabled && primary.traitOptions && primary.traitOptions.length > 0 && (
                  <div className="field">
                    <label>Secondary traits</label>
                    <div className="type-chips" role="listbox" aria-label="Project traits">
                      {primary.traitOptions.map((trait) => (
                        <button
                          key={trait}
                          type="button"
                          role="option"
                          aria-selected={traits.includes(trait)}
                          className={traits.includes(trait) ? "primary" : ""}
                          onClick={() => toggleTrait(trait)}
                        >
                          {trait.replace(/_/g, " ")}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                <div className="gen-grid">
                  <div className="field">
                    <label htmlFor="np-aspect">Aspect</label>
                    <select id="np-aspect" value={aspect} onChange={(e) => setAspect(e.target.value)}>
                      {["16:9", "9:16", "2.39:1", "1:1", "21:9"].map((a) => (
                        <option key={a} value={a}>
                          {a}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="np-resolution">Resolution</label>
                    <select
                      id="np-resolution"
                      value={resolution}
                      onChange={(e) => setResolution(e.target.value)}
                    >
                      {["720p", "1080p", "1440p", "4K"].map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="np-fps">FPS</label>
                    <select id="np-fps" value={fps} onChange={(e) => setFps(e.target.value)}>
                      {["auto", "24", "25", "30"].map((f) => (
                        <option key={f} value={f}>
                          {f === "auto" ? "Recommended (24 fps)" : f}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="np-style">Storyboard style</label>
                    <select id="np-style" value={style} onChange={(e) => setStyle(e.target.value)}>
                      {STORYBOARD_STYLES.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="np-video-gen">Preferred video generator</label>
                    <select
                      id="np-video-gen"
                      value={preferredGen}
                      onChange={(e) => setPreferredGen(e.target.value)}
                      data-testid="create-project-optional-last-control"
                    >
                      {videoGens.length === 0 && <option value="automatic">Loading…</option>}
                      {videoGens.map((g) => (
                        <option key={g.id} value={g.id} disabled={!g.available}>
                          {g.label} {!g.available ? "(unavailable)" : ""}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            )}
            {templatesOpen && onSelectTemplate ? (
              <div
                ref={templatesPanelRef}
                id="create-project-templates-panel"
                className="new-production-card__templates-panel"
                data-testid="create-project-templates-panel"
              >
                <p className="muted" style={{ margin: 0 }}>
                  Pick a production shape to start with ready-made defaults.
                </p>
                <div className="new-production-card__templates-list" role="list">
                  {PROJECT_TEMPLATES.map((template, index) => (
                    <button
                      key={template.id}
                      type="button"
                      className="new-production-card__template-option"
                      role="listitem"
                      disabled={busy}
                      data-testid={`create-project-template-${template.id}`}
                      data-last-template={index === PROJECT_TEMPLATES.length - 1 ? "true" : undefined}
                      onClick={() => onSelectTemplate(template.id)}
                    >
                      <strong>{template.title}</strong>
                      <span>{template.description}</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>
        <div className="new-production-card__footer">
          {error ? (
            <p className="new-production-card__submit-error" role="alert" data-testid="create-project-error">
              {error}
            </p>
          ) : null}
          <div className="new-production-card__footer-actions">
            <button
              type="button"
              className="ghost"
              onClick={onCancel}
              disabled={busy}
              data-testid="create-project-cancel"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="primary"
              disabled={!canSubmit}
              data-testid="create-project-submit"
            >
              {busy ? "Creating…" : "Create Project"}
            </button>
          </div>
        </div>
      </form>
    </section>
  );
}

export function ProjectTemplateCard({
  title,
  description,
  imageMotif,
  imageSrc,
  imageAlt,
  busy,
  onUse,
}: {
  title: string;
  description: string;
  imageMotif: string;
  imageSrc: string;
  imageAlt: string;
  busy: boolean;
  onUse: () => void;
}) {
  return (
    <article className="dash-card template-card">
      <div className={`cinematic-media ${imageMotif} template-cover`} role="img" aria-label={imageAlt}>
        <div className="cinematic-media-fallback" aria-hidden="true" />
        <img
          src={imageSrc}
          alt=""
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = "none";
          }}
        />
        <div className="cinematic-media-overlay" />
        <h3>{title}</h3>
      </div>
      <p>{description}</p>
      <button type="button" className="primary" disabled={busy} onClick={onUse}>
        Use Template
      </button>
    </article>
  );
}
