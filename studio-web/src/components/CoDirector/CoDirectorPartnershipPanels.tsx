import { useEffect, useState } from "react";
import { api } from "../../api";
import { Button } from "../ui";
import { useCoDirectorSession } from "./CoDirectorSession";

type PartnershipBundle = {
  deliverables?: Array<Record<string, unknown>>;
  pitches?: Array<Record<string, unknown>>;
  vision?: Record<string, unknown>;
  marketing?: Record<string, unknown>;
  journey?: Record<string, unknown>;
  collaboration?: Record<string, unknown>;
};

function usePartnership() {
  const { uiContext } = useCoDirectorSession();
  const projectId = uiContext.projectId || "";
  const [bundle, setBundle] = useState<PartnershipBundle | null>(null);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    api
      .getCoDirectorPartnership(projectId)
      .then((body) => {
        if (!cancelled) setBundle((body.partnership || {}) as PartnershipBundle);
      })
      .catch(() => {
        if (!cancelled) setBundle(null);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  return { projectId, bundle, setBundle };
}

export function CoDirectorDevelopmentPanel() {
  const { projectId, bundle, setBundle } = usePartnership();
  const deliverables = bundle?.deliverables || [];

  async function act(action: string, deliverableId: string) {
    if (!projectId) return;
    const res = await api.partnershipDeliverableAction(projectId, { action, deliverableId });
    if (res.partnership) setBundle(res.partnership as PartnershipBundle);
  }

  if (!projectId) return <p className="muted">Select a project to open Development.</p>;

  return (
    <div data-testid="codirector-content-development">
      <h3 style={{ marginTop: 0, fontSize: "0.95rem" }}>Development</h3>
      <p className="muted">Story templates, treatments, and drafts — review before anything is locked.</p>
      {deliverables.length === 0 ? (
        <p className="muted">No drafts yet. When enough of the idea is clear, Co-Director will offer a preview here.</p>
      ) : (
        deliverables.map((d) => (
          <article key={String(d.id)} className="codirector-content-card" style={{ marginTop: "0.5rem" }}>
            <p>
              <strong>{String(d.title || d.type)}</strong> · {String(d.status)}
            </p>
            {d.why_now ? <p className="muted">{String(d.why_now)}</p> : null}
            <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>
              {String(d.content || d.preview_content || "")}
            </pre>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
              <Button compact onClick={() => void act("approve", String(d.id))}>
                Approve
              </Button>
              <Button compact variant="ghost" onClick={() => void act("reject", String(d.id))}>
                Reject
              </Button>
            </div>
          </article>
        ))
      )}
    </div>
  );
}

export function CoDirectorVisionPanel() {
  const { projectId, bundle } = usePartnership();
  const vision = bundle?.vision || {};
  const journey = bundle?.journey || {};

  if (!projectId) return <p className="muted">Select a project to open Vision.</p>;

  return (
    <div data-testid="codirector-content-vision">
      <h3 style={{ marginTop: 0, fontSize: "0.95rem" }}>Vision & Audience</h3>
      <p className="muted">Where this project is headed — kept open until you decide.</p>
      <p>
        Destination: <strong>{String(vision.primary_destination || "UNDECIDED")}</strong>
      </p>
      <p className="muted">Scale: {String(vision.project_scale || "UNDECIDED")}</p>
      <p className="muted">Commercial intent: {String(vision.commercial_intent || "UNDECIDED")}</p>
      {Array.isArray(vision.intended_audience) && vision.intended_audience.length ? (
        <p>Audience: {(vision.intended_audience as string[]).join(", ")}</p>
      ) : null}
      {Array.isArray(vision.conflicts) && vision.conflicts.length ? (
        <div>
          <p>Tradeoffs to consider:</p>
          <ul>
            {(vision.conflicts as string[]).map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <p className="muted">Journey stage: {String(journey.current_stage || "—")}</p>
    </div>
  );
}

export function CoDirectorPitchLaunchPanel() {
  const { projectId, bundle } = usePartnership();
  const pitches = bundle?.pitches || [];
  const marketing = bundle?.marketing || {};

  if (!projectId) return <p className="muted">Select a project to open Pitch & Launch.</p>;

  return (
    <div data-testid="codirector-content-pitch">
      <h3 style={{ marginTop: 0, fontSize: "0.95rem" }}>Pitch & Launch</h3>
      <p className="muted">Pitches and marketing ideas from the project’s strengths — never silently approved.</p>
      {pitches.length === 0 ? (
        <p className="muted">No pitch drafts yet.</p>
      ) : (
        pitches.map((p) => (
          <article key={String(p.id)} className="codirector-content-card" style={{ marginTop: "0.5rem" }}>
            <p>
              <strong>{String(p.pitch_type)}</strong> · {String(p.status)}
            </p>
            <p>{String(p.logline || "")}</p>
            <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>{String(p.short_pitch || "")}</pre>
          </article>
        ))
      )}
      {marketing.positioning_statement || (Array.isArray(marketing.key_hooks) && marketing.key_hooks.length) ? (
        <article className="codirector-content-card" style={{ marginTop: "0.75rem" }}>
          <p>
            <strong>Marketing notes</strong> · {String(marketing.status || "EMERGING")}
          </p>
          {marketing.positioning_statement ? <p>{String(marketing.positioning_statement)}</p> : null}
          {Array.isArray(marketing.key_hooks) ? (
            <ul>
              {(marketing.key_hooks as string[]).slice(0, 5).map((h) => (
                <li key={h}>{h}</li>
              ))}
            </ul>
          ) : null}
        </article>
      ) : null}
    </div>
  );
}

export function CoDirectorDeliverableReview() {
  const { activity } = useCoDirectorSession();
  const deliverable = activity?.activeDeliverable;
  if (!deliverable || !Object.keys(deliverable).length) return null;
  const status = String(deliverable.status || "");
  const preview = String(deliverable.preview_content || "");
  const content = String(deliverable.content || "");
  const why = String(deliverable.why_now || "");

  return (
    <section
      className="codirector-content-card"
      data-testid="codirector-deliverable-review"
      aria-label="Draft review"
      style={{ marginBottom: "0.75rem" }}
    >
      <p className="eyebrow">{status === "PREVIEW" ? "Preview" : "Draft for review"}</p>
      <p>
        <strong>{String(deliverable.title || deliverable.type)}</strong>
      </p>
      {why ? <p className="muted">{why}</p> : null}
      <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>{content || preview}</pre>
      <p className="muted">Not approved until you say so.</p>
    </section>
  );
}
