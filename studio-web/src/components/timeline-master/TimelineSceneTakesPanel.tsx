import { useMemo, useState } from "react";
import { api } from "../../api";
import type { SceneTimelineMaster } from "../../timelineMaster/contracts";
import { sceneTakeDisplayLabel, sceneTakeIsListed } from "../../timelineMaster/sceneTakes";
import { HelpTip } from "../HelpTip";

function takeStatusText(
  take: NonNullable<SceneTimelineMaster["sceneTakes"]>[number],
  master: SceneTimelineMaster,
): string {
  const isActiveRender = take.id === master.activeSceneTakeId && take.status === "rendering";
  if (isActiveRender) {
    const gp = master.generationProgress;
    const n = gp?.currentBatchIndex || 1;
    const m = gp?.totalBatches || take.batches?.length || 1;
    const pct = Math.round(Number(gp?.batchProgress || 0) * 100);
    return `Rendering ${n}/${m} — ${pct}%`;
  }
  if (take.status === "rendering") return "Ready";
  if (take.status === "cancelled") return "Cancelled";
  if (take.status === "incomplete") return "Incomplete";
  if (take.id === master.currentSceneTakeId) return "Current";
  return "Ready";
}

function qualityLine(take: NonNullable<SceneTimelineMaster["sceneTakes"]>[number]): string {
  const q = take.quality;
  if (!q) return "";
  const bits: string[] = [];
  if (q.h3Megapixels != null) bits.push(`H3 ${q.h3Megapixels} MP`);
  if (q.width && q.height) bits.push(`${q.width}×${q.height}`);
  if (q.ltxQuality) bits.push(`LTX ${q.ltxQuality}`);
  return bits.join(" · ");
}

export function TimelineSceneTakesPanel({
  projectId,
  sceneId,
  master,
  previewTakeId,
  onPreviewTake,
  onRefresh,
  onError,
  onGenerationStandby,
}: {
  projectId: string;
  sceneId: string;
  master: SceneTimelineMaster;
  previewTakeId: string | null;
  onPreviewTake: (takeId: string | null) => void;
  onRefresh: () => void | Promise<void>;
  onError?: (message: string) => void;
  onGenerationStandby?: (standby: boolean) => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const takes = (master.sceneTakes || []).filter(sceneTakeIsListed);
  const rendering = (master.sceneTakes || []).some(
    (take) => take.id === master.activeSceneTakeId && take.status === "rendering",
  );
  const rows = useMemo(() => [...takes].sort((a, b) => a.letterIndex - b.letterIndex), [takes]);

  const run = async (key: string, work: () => Promise<void>) => {
    if (busy) return;
    setBusy(key);
    try {
      await work();
      await onRefresh();
    } catch (error) {
      onError?.(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="timeline-scene-takes" data-testid="timeline-scene-takes">
      <p className="scene-meta">
        A new take remakes the whole scene. Re-Take on the Preview Monitor changes only a marked part of the current take.
        <HelpTip text="Takes keep earlier full-scene renders. Current is what Preview and Publish use." />
      </p>
      <button
        type="button"
        className="primary"
        data-testid="timeline-new-take"
        disabled={Boolean(busy) || rendering}
        onClick={() =>
          void run("new", async () => {
            onGenerationStandby?.(true);
            try {
              await api.directorTimelineNewSceneTake(projectId, sceneId);
            } catch (error) {
              onGenerationStandby?.(false);
              throw error;
            }
          })
        }
      >
        {busy === "new" ? "Starting…" : "+ New Take"}
      </button>
      <ul className="timeline-scene-takes__list">
        {rows.map((take) => {
          const current = take.id === master.currentSceneTakeId;
          const published = take.id === master.scenePublish?.takeId || Boolean(take.publishedAssetId);
          const previewing = previewTakeId === take.id;
          const status = takeStatusText(take, master);
          const quality = qualityLine(take);
          return (
            <li
              key={take.id}
              className={`timeline-scene-takes__row${current ? " is-current" : ""}${previewing ? " is-previewing" : ""}`}
              data-testid={`timeline-scene-take-${take.label}`}
            >
              <div className="timeline-scene-takes__meta">
                <strong>{sceneTakeDisplayLabel(take.label)}</strong>
                <span className="scene-meta">{status}</span>
                {published ? <span className="scene-meta">Published</span> : null}
                {quality ? <span className="scene-meta">{quality}</span> : null}
              </div>
              <div className="timeline-scene-takes__actions">
                <button
                  type="button"
                  data-testid={`timeline-take-preview-${take.label}`}
                  disabled={!take.batches?.some((m) => m.assetId) && !take.resultAssetId}
                  onClick={() => onPreviewTake(previewing && !current ? null : take.id)}
                >
                  Preview
                </button>
                <button
                  type="button"
                  data-testid={`timeline-take-current-${take.label}`}
                  disabled={current || take.status === "rendering" || busy === take.id}
                  onClick={() =>
                    void run(take.id, async () => {
                      await api.directorTimelineMakeSceneTakeCurrent(projectId, sceneId, take.id);
                      onPreviewTake(null);
                    })
                  }
                >
                  Make Current
                </button>
                {take.status === "incomplete" || take.status === "cancelled" ? (
                  <button
                    type="button"
                    data-testid={`timeline-take-resume-${take.label}`}
                    disabled={Boolean(busy) || rendering}
                    onClick={() =>
                      void run(`resume-${take.id}`, async () => {
                        await api.directorTimelineResumeSceneTake(projectId, sceneId, take.id);
                      })
                    }
                  >
                    Resume
                  </button>
                ) : null}
                <button
                  type="button"
                  className="ghost"
                  data-testid={`timeline-take-delete-${take.label}`}
                  disabled={current || published || Boolean(busy)}
                  title={
                    current
                      ? "Make another take current before deleting this one."
                      : published
                        ? "This take is published."
                        : "Delete this take"
                  }
                  onClick={() =>
                    void run(`del-${take.id}`, async () => {
                      await api.directorTimelineDeleteSceneTake(projectId, sceneId, take.id);
                      if (previewTakeId === take.id) onPreviewTake(null);
                    })
                  }
                >
                  Delete
                </button>
              </div>
            </li>
          );
        })}
      </ul>
      {rows.length === 0 ? <p className="scene-meta">Generate the scene once to create Take A.</p> : null}
    </div>
  );
}
