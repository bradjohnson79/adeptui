import { useState } from "react";
import { PRODUCTION_TYPES, type ProductionType } from "../../dashboardImages";

export function NewProductionCard({
  busy,
  onCreate,
}: {
  busy: boolean;
  onCreate: (opts: {
    name: string;
    type: ProductionType;
    aspect?: string;
    resolution?: string;
    fps?: number | "auto";
    storyboard_style?: string;
  }) => void;
}) {
  const [name, setName] = useState("Untitled Project");
  const [type, setType] = useState<ProductionType>("Short Film");
  const [advanced, setAdvanced] = useState(false);
  const [aspect, setAspect] = useState("16:9");
  const [resolution, setResolution] = useState("1080p");
  const [fps, setFps] = useState<string>("auto");
  const [style, setStyle] = useState("Pencil storyboard");

  return (
    <section className="dash-card new-production-card" id="new-production">
      <p className="eyebrow">New production</p>
      <h2>Start from scratch or choose a template</h2>
      <p className="muted">Name your film, pick a production type, then open the command center.</p>
      <div className="field">
        <label htmlFor="np-name">Project name</label>
        <input id="np-name" value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="field">
        <label>Production type</label>
        <div className="type-chips" role="listbox" aria-label="Production type">
          {PRODUCTION_TYPES.map((t) => (
            <button
              key={t}
              type="button"
              role="option"
              aria-selected={type === t}
              className={type === t ? "primary" : ""}
              onClick={() => setType(t)}
            >
              {t}
            </button>
          ))}
        </div>
      </div>
      <button type="button" className="ghost" onClick={() => setAdvanced((v) => !v)}>
        {advanced ? "Hide" : "Show"} optional defaults
      </button>
      {advanced && (
        <div className="gen-grid" style={{ marginTop: "0.75rem" }}>
          <div className="field">
            <label>Aspect</label>
            <select value={aspect} onChange={(e) => setAspect(e.target.value)}>
              {["16:9", "9:16", "2.39:1", "1:1"].map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Resolution</label>
            <select value={resolution} onChange={(e) => setResolution(e.target.value)}>
              {["720p", "1080p", "1440p", "4K"].map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>FPS</label>
            <select value={fps} onChange={(e) => setFps(e.target.value)}>
              {["auto", "24", "25", "30"].map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Storyboard style</label>
            <select value={style} onChange={(e) => setStyle(e.target.value)}>
              {["Pencil storyboard", "Grayscale cinematic", "Color concept frame", "Anime storyboard"].map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}
      <div className="row" style={{ marginTop: "1rem" }}>
        <button
          type="button"
          className="primary"
          disabled={busy}
          onClick={() =>
            onCreate({
              name: name.trim() || "Untitled Project",
              type,
              aspect,
              resolution,
              fps: fps === "auto" ? "auto" : Number(fps),
              storyboard_style: style,
            })
          }
        >
          {busy ? "Creating…" : "Create Project"}
        </button>
        <a href="#templates" className="button-link">
          <button type="button">Browse Templates</button>
        </a>
      </div>
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
