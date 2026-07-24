import { useState } from "react";
import type { DashboardImage } from "../../dashboardImages";
import type { EditorTab } from "../../workspacePrefs";

export function ProductionStatCard({
  value,
  label,
  hint,
  highlight = false,
}: {
  value: string | number;
  label: string;
  hint?: string;
  highlight?: boolean;
}) {
  return (
    <div className={`dash-card production-stat ${highlight ? "highlight" : ""}`}>
      <strong>{value}</strong>
      <span>{label}</span>
      {hint && <small className="muted">{hint}</small>}
    </div>
  );
}

export function WorkspaceFeatureCard({
  title,
  description,
  status,
  image,
  onContinue,
}: {
  title: string;
  description: string;
  status?: string;
  image: DashboardImage;
  tab?: EditorTab;
  onContinue: () => void;
}) {
  return (
    <button type="button" className="dash-card workspace-feature-card" onClick={onContinue}>
      <div className={`cinematic-media ${image.motif}`}>
        <div className="cinematic-media-fallback" aria-hidden="true" />
        <img
          src={image.src}
          alt=""
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = "none";
          }}
        />
        <div className="cinematic-media-overlay" />
        <div className="workspace-feature-copy">
          <h3>{title}</h3>
          {status && <span className="pill">{status}</span>}
          <p>{description}</p>
        </div>
      </div>
    </button>
  );
}

export function ContinueProductionCard({
  title,
  subtitle,
  bullets,
  onContinue,
  imageSrc,
}: {
  title: string;
  subtitle: string;
  bullets: string[];
  onContinue: () => void;
  imageSrc?: string | null;
}) {
  return (
    <section className="dash-card continue-production-card">
      <div className="continue-copy">
        <p className="eyebrow">Continue where you left off</p>
        <h2>{title}</h2>
        <p className="muted">{subtitle}</p>
        <ul>
          {bullets.map((b) => (
            <li key={b}>{b}</li>
          ))}
        </ul>
        <button type="button" className="primary" onClick={onContinue}>
          Continue Production
        </button>
      </div>
      <div className="cinematic-media motif-director continue-media">
        <div className="cinematic-media-fallback" aria-hidden="true" />
        {imageSrc && (
          <img
            src={imageSrc}
            alt=""
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = "none";
            }}
          />
        )}
        <div className="cinematic-media-overlay" />
      </div>
    </section>
  );
}

export function CoDirectorBriefing({
  items,
  onAsk,
  onPrimary,
  primaryLabel,
}: {
  items: { id: string; text: string }[];
  onAsk: () => void;
  onPrimary?: () => void;
  primaryLabel?: string;
}) {
  return (
    <section className="dash-card codirector-briefing">
      <p className="eyebrow">Co-Director Briefing</p>
      <h2>What to do next</h2>
      {!items.length ? (
        <p className="muted">
          Your production is quiet. Ask Co-Director to propose the next scene, storyboard, or spatial block.
        </p>
      ) : (
        <ul>
          {items.map((i) => (
            <li key={i.id}>{i.text}</li>
          ))}
        </ul>
      )}
      <div className="row" style={{ marginTop: "0.75rem", flexWrap: "wrap", gap: "0.4rem" }}>
        {onPrimary && primaryLabel && (
          <button type="button" className="primary" onClick={onPrimary}>
            {primaryLabel}
          </button>
        )}
        <button type="button" onClick={onAsk}>
          Ask Co-Director
        </button>
      </div>
    </section>
  );
}

export function ProductionHealthPanel({
  items,
  onReview,
}: {
  items: { level: string; text: string }[];
  onReview?: () => void;
}) {
  return (
    <section className="dash-card">
      <h2>Production Health</h2>
      {!items.length ? (
        <p className="muted">Looking healthy — ComfyUI, profiles, and continuity checks are clear.</p>
      ) : (
        <ul className="health-list">
          {items.map((h, i) => (
            <li key={i}>
              <span className={`status-badge ${h.level === "warn" ? "warn" : h.level === "bad" ? "bad" : "ok"}`}>
                {h.level === "warn" ? "△" : h.level === "bad" ? "!" : "✓"}
              </span>{" "}
              {h.text}
            </li>
          ))}
        </ul>
      )}
      {onReview && (
        <button type="button" style={{ marginTop: "0.75rem" }} onClick={onReview}>
          Review Issues
        </button>
      )}
    </section>
  );
}

export function ActivityFeed({
  items,
}: {
  items: { id: string; when: string; text: string }[];
}) {
  return (
    <section className="dash-card">
      <h2>Recent Activity</h2>
      {!items.length ? (
        <p className="muted">Activity will appear as you generate, approve, and assemble.</p>
      ) : (
        <ul className="activity-feed">
          {items.map((a) => (
            <li key={a.id}>
              <span className="scene-meta">{a.when}</span>
              <span>{a.text}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function RecentAssetCard({
  name,
  kind,
  thumb,
  meta,
  onOpen,
}: {
  name: string;
  kind: string;
  thumb?: string;
  meta?: string;
  onOpen: () => void;
}) {
  return (
    <button type="button" className="recent-asset-card" onClick={onOpen}>
      <div className="recent-asset-thumb">
        {thumb ? <img src={thumb} alt="" /> : <span className="library-card-fallback">{kind}</span>}
      </div>
      <span className="recent-asset-name">{name}</span>
      <span className="scene-meta">{meta || kind}</span>
    </button>
  );
}

export function RenderJobCard({
  title,
  status,
  progress,
  message,
  thumb,
  onOpen,
}: {
  title: string;
  status: string;
  progress: number;
  message?: string;
  thumb?: string;
  onOpen?: () => void;
}) {
  return (
    <div className="render-job-card">
      {thumb && <img src={thumb} alt="" className="render-job-thumb" />}
      <div className="render-job-body">
        <strong>{title}</strong>
        <span className={`status-badge ${status === "failed" ? "bad" : status === "done" ? "ok" : "warn"}`}>
          {status}
        </span>
        <div className="progress-strip" aria-hidden="true">
          <div className="progress-strip-fill" style={{ width: `${Math.round(progress * 100)}%` }} />
        </div>
        <p className="scene-meta">{message}</p>
        {onOpen && (
          <button type="button" onClick={onOpen}>
            Open
          </button>
        )}
      </div>
    </div>
  );
}

export function CoDirectorComposer({
  onSubmit,
}: {
  onSubmit: (text: string) => void;
}) {
  const [text, setText] = useState("");
  const examples = [
    "Create a dialogue scene with two characters.",
    "Turn Scene 1 into a storyboard.",
    "Continue the last Spatial Map.",
    "Build a Director timeline from approved panels.",
  ];
  return (
    <section className="dash-card codirector-composer" id="codirector">
      <p className="eyebrow">Co-Director</p>
      <h2>What would you like to create?</h2>
      <textarea
        rows={3}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Describe a scene, storyboard, or production next step…"
      />
      <div className="example-prompts">
        {examples.map((ex) => (
          <button key={ex} type="button" className="ghost" onClick={() => setText(ex)}>
            {ex}
          </button>
        ))}
      </div>
      <button
        type="button"
        className="primary"
        disabled={!text.trim()}
        onClick={() => {
          onSubmit(text.trim());
          setText("");
        }}
      >
        Ask Co-Director
      </button>
    </section>
  );
}
