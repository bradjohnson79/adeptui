import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import { MiniMaxH3PlanPanel } from "../minimax-h3/MiniMaxH3PlanPanel";

const DEFAULT_BASELINE_PROMPT =
  "A glowing glass bottle on a dark studio table, slow cinematic push-in, subtle condensation, controlled rim lighting.";

const DEFAULT_DELTA =
  "Keep the bottle, framing, camera direction, duration, and lighting continuity. Make the camera push-in slightly slower and add a stronger condensation shimmer. Do not change the product design or background.";

type TakeRow = {
  takeId: string;
  label?: string;
  takeNumber?: number;
  assetId?: string | null;
  jobId?: string | null;
  retake?: boolean;
  sourceTakeId?: string | null;
  provenance?: Record<string, unknown>;
};

type ShotState = {
  shotId: string;
  takes: TakeRow[];
  activeTakeId?: string | null;
  originalPrompt?: string;
  editHistory?: Array<Record<string, unknown>>;
};

export function TimelineRetakeDrawer({
  projectId,
  sceneId,
  shotId,
  baselinePrompt,
  baselineAssetId,
  baselineJobId,
  open,
  onClose,
}: {
  projectId: string;
  sceneId: string;
  shotId: string;
  baselinePrompt?: string;
  baselineAssetId?: string | null;
  baselineJobId?: string | null;
  open: boolean;
  onClose: () => void;
}) {
  const [shot, setShot] = useState<ShotState | null>(null);
  const [delta, setDelta] = useState(DEFAULT_DELTA);
  const [message, setMessage] = useState<string | null>(null);
  const [completedJob, setCompletedJob] = useState<{
    jobId: string;
    assetId?: string | null;
    provenance?: Record<string, unknown>;
  } | null>(null);
  const [engine] = useState("MiniMax H3");

  const prompt = baselinePrompt || shot?.originalPrompt || DEFAULT_BASELINE_PROMPT;

  const refresh = useCallback(async () => {
    const res = await api.timelineRetakes.getShot(projectId, shotId);
    setShot(res.shot || null);
  }, [projectId, shotId]);

  useEffect(() => {
    if (!open) return;
    void (async () => {
      try {
        await api.timelineRetakes.ensureBaseline(projectId, {
          shotId,
          sceneId,
          assetId: baselineAssetId || null,
          jobId: baselineJobId || null,
          prompt,
          durationSec: 5,
          provenance: {
            engine: "MiniMax H3",
            deployment: "private-local",
            access: "owner-only",
            runtime: "route-a",
            apiUsed: false,
            ltxUsed: false,
          },
        });
        await refresh();
      } catch (e) {
        setMessage(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [open, projectId, shotId, sceneId, baselineAssetId, baselineJobId, prompt, refresh]);

  if (!open) return null;

  const sourceTakeId = shot?.activeTakeId || shot?.takes?.[0]?.takeId || null;

  return (
    <div
      className="timeline-retake-drawer"
      role="dialog"
      aria-modal="true"
      aria-label="Timeline Re-take"
      data-testid="timeline-retake-drawer"
      style={{
        border: "1px solid var(--border, #333)",
        borderRadius: 12,
        padding: "1rem",
        marginTop: "1rem",
        background: "var(--panel, #121212)",
      }}
    >
      <header style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem" }}>
        <div>
          <h3>Re-take</h3>
          <p>Preserve the approved shot. Change one bounded creative instruction. Engine: {engine} (explicit).</p>
        </div>
        <button type="button" data-testid="timeline-retake-close" onClick={onClose} aria-label="Close Re-take">
          ×
        </button>
      </header>

      <p data-testid="timeline-retake-engine">
        <strong>MiniMax H3</strong> — Private Local · Owner Only · Experimental · Route A
      </p>

      <label>
        Continuity change
        <span title="Keep the product, framing, and lighting. Describe only the small change you want."> (?)</span>
        <textarea
          data-testid="timeline-retake-delta"
          value={delta}
          onChange={(e) => setDelta(e.target.value)}
          rows={4}
          style={{ width: "100%", marginTop: "0.35rem" }}
          aria-label="Re-take continuity instruction"
        />
      </label>

      <MiniMaxH3PlanPanel
        projectId={projectId}
        prompt={prompt}
        originalPrompt={prompt}
        mode="text-to-video"
        sourceSurface="timeline-retake"
        sceneId={sceneId}
        shotId={shotId}
        durationSec={5}
        retake
        sourceTakeId={sourceTakeId}
        deltaInstruction={delta}
        onJobTerminal={(job) => {
          if (job.status === "cancelled") {
            setMessage("Re-take cancelled. No alternate take was added. Original shot unchanged.");
            setCompletedJob(null);
            return;
          }
          if (job.status === "completed") {
            const media = job.media || {};
            const lib = (media.libraryImport || {}) as { assetId?: string };
            setCompletedJob({
              jobId: job.jobId,
              assetId: lib.assetId || null,
              provenance: { ...(job.provenance || {}), status: job.status },
            });
            setMessage("Re-take ready. Choose how to place it — nothing replaces Take 1 until you decide.");
          }
          if (job.status === "failed") {
            setMessage(job.errorMessage || "Re-take failed. Original take remains.");
          }
        }}
      />

      {completedJob && sourceTakeId && (
        <div data-testid="timeline-retake-result-actions" style={{ marginTop: "0.85rem" }}>
          <p>Place this Re-take:</p>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <button
              type="button"
              data-testid="timeline-retake-add-alternate"
              onClick={() => {
                void api.timelineRetakes
                  .addAlternate(projectId, {
                    shotId,
                    sourceTakeId,
                    assetId: completedJob.assetId,
                    jobId: completedJob.jobId,
                    prompt,
                    deltaInstruction: delta,
                    durationSec: 5,
                    provenance: {
                      ...completedJob.provenance,
                      retake: true,
                      sourceTakeId,
                      apiUsed: false,
                      ltxUsed: false,
                      engine: "MiniMax H3",
                      deployment: "private-local",
                      access: "owner-only",
                      runtime: "route-a",
                    },
                    activate: false,
                  })
                  .then(() => refresh())
                  .then(() => setMessage("Added as Alternate Take. Take 1 preserved."))
                  .catch((e) => setMessage(e instanceof Error ? e.message : String(e)));
              }}
            >
              Add as Alternate Take
            </button>
            <button
              type="button"
              data-testid="timeline-retake-replace"
              onClick={() => {
                void api.timelineRetakes
                  .addAlternate(projectId, {
                    shotId,
                    sourceTakeId,
                    assetId: completedJob.assetId,
                    jobId: completedJob.jobId,
                    prompt,
                    deltaInstruction: delta,
                    durationSec: 5,
                    provenance: {
                      ...completedJob.provenance,
                      retake: true,
                      sourceTakeId,
                      apiUsed: false,
                      ltxUsed: false,
                    },
                    activate: true,
                  })
                  .then(() => refresh())
                  .then(() => setMessage("Replaced active take. Prior take kept in history."))
                  .catch((e) => setMessage(e instanceof Error ? e.message : String(e)));
              }}
            >
              Replace Current Take
            </button>
            <button
              type="button"
              data-testid="timeline-retake-keep-original"
              onClick={() => {
                setCompletedJob(null);
                setMessage("Kept original. New media stays in Library only — not linked as a take.");
              }}
            >
              Keep Original
            </button>
          </div>
        </div>
      )}

      {shot && (
        <div data-testid="timeline-retake-takes" style={{ marginTop: "1rem" }}>
          <h4>Takes</h4>
          <ul style={{ listStyle: "none", padding: 0 }}>
            {(shot.takes || []).map((t) => (
              <li key={t.takeId} data-testid={`timeline-take-${t.takeId}`} style={{ marginBottom: "0.4rem" }}>
                <strong>{t.label || t.takeId}</strong>
                {shot.activeTakeId === t.takeId ? " · Active" : ""}
                {t.retake ? " · Re-take" : " · Baseline"}
                {shot.activeTakeId !== t.takeId && (
                  <button
                    type="button"
                    data-testid={`timeline-take-activate-${t.takeId}`}
                    style={{ marginLeft: "0.5rem" }}
                    onClick={() =>
                      void api.timelineRetakes
                        .setActive(projectId, shotId, t.takeId)
                        .then(() => refresh())
                        .then(() => setMessage(`Active take: ${t.label || t.takeId}`))
                    }
                  >
                    Make active
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {message && (
        <p role="status" data-testid="timeline-retake-message">
          {message}
        </p>
      )}
    </div>
  );
}
