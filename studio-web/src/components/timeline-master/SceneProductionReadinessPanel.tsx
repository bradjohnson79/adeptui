import { useTimelineContextPackage } from "./useTimelineContextPackage";
import type { Project, Scene } from "../../types";

/**
 * SceneProductionReadinessPanel — read-only display of scene readiness
 * consumed from the Co-Director-owned Production Readiness Service
 * (PRODUCTION_READINESS_OWNED_BY_CODIRECTOR). The Timeline displays this;
 * it never computes readiness itself.
 */
export function SceneProductionReadinessPanel({
  project,
  scene,
}: {
  project: Project;
  scene: Scene;
}) {
  const { pkg, loading, error } = useTimelineContextPackage(project.id, scene.id, "production");

  if (loading) {
    return (
      <div className="timeline-inspector__stack" data-testid="scene-readiness-panel">
        <strong>Production Readiness</strong>
        <p className="scene-meta">Checking readiness…</p>
      </div>
    );
  }

  if (error || !pkg || !pkg.ok || !pkg.package) {
    return (
      <div className="timeline-inspector__stack" data-testid="scene-readiness-panel">
        <strong>Production Readiness</strong>
        <p className="scene-meta" data-testid="scene-readiness-unavailable">
          {error || pkg?.error || "Readiness unavailable. Editing remains available."}
        </p>
      </div>
    );
  }

  const p = pkg.package;
  const r = p.readiness;
  const gateLabel =
    p.gateLevel === "PRODUCTION_LOCK"
      ? "Locked"
      : p.gateLevel === "PRODUCTION_WARNING"
        ? "Warning"
        : "Exploration";

  return (
    <div className="timeline-inspector__stack" data-testid="scene-readiness-panel">
      <strong>Production Readiness</strong>
      <div className="scene-meta">
        Status: <span data-testid="scene-readiness-status">{r.status}</span> · Gate:{" "}
        <span data-testid="scene-readiness-gate">{gateLabel}</span>
      </div>
      {r.blockerSummary ? (
        <p className="scene-meta" data-testid="scene-readiness-blocker">
          {r.blockerSummary}
        </p>
      ) : null}
      <div className="timeline-inspector__meta-grid">
        <div>
          <strong>Cast</strong>
          <div className="scene-meta">{r.castReady ? "Ready" : "Not ready"}</div>
        </div>
        <div>
          <strong>Location</strong>
          <div className="scene-meta">{r.locationReady ? "Ready" : "Not ready"}</div>
        </div>
        <div>
          <strong>References</strong>
          <div className="scene-meta">{r.imageReferencesReady ? "Ready" : "Not ready"}</div>
        </div>
        <div>
          <strong>Voice</strong>
          <div className="scene-meta">{r.voiceReady ? "Ready" : "Not ready"}</div>
        </div>
      </div>
      {p.characters.length > 0 && (
        <details>
          <summary className="scene-meta">Cast ({p.characters.length})</summary>
          <ul className="scene-meta">
            {p.characters.map((c) => (
              <li key={c.characterId}>
                {c.name} — {c.castStatus}
                {c.locked ? " · locked" : ""}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
