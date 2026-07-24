import { useEffect, useRef, useState } from "react";
import type { Job, Project, Scene } from "../types";
import { api } from "../api";
import { aspectCssValue } from "../workspacePrefs";
import { PanelHeading } from "./HelpTip";

export type PreviewMonitorState =
  | "idle"
  | "preparing"
  | "live_preview"
  | "processing"
  | "assembling"
  | "post"
  | "complete"
  | "failed"
  | "cancelled";

type PreviewPayload = {
  jobId?: string;
  sceneId?: string;
  engineId?: string;
  sequenceNumber?: number;
  stage?: string;
  progress?: number;
  mediaType?: string;
  sourceUrl?: string;
  localPath?: string;
};

export function LivePreviewMonitor({
  project,
  scene,
  fitMode = "contain",
}: {
  project: Project;
  scene?: Scene;
  fitMode?: "contain" | "cover" | "none";
}) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [preview, setPreview] = useState<PreviewPayload | null>(null);
  const [seq, setSeq] = useState(0);
  const [hideOverlay, setHideOverlay] = useState(false);
  const [pauseUpdates, setPauseUpdates] = useState(false);
  const [announce, setAnnounce] = useState("");
  const objectUrlRef = useRef<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const activeJob =
    jobs.find(
      (j) =>
        j.scene_id === scene?.id &&
        (j.status === "queued" || j.status === "running")
    ) ||
    jobs.find((j) => j.scene_id === scene?.id) ||
    null;

  const monitorState: PreviewMonitorState = (() => {
    if (!activeJob) {
      if (scene?.lipsync_output_path || scene?.output_path) return "complete";
      return "idle";
    }
    if (activeJob.status === "failed") return "failed";
    if (activeJob.status === "cancelled") return "cancelled";
    if (activeJob.status === "done") return "complete";
    const stage = (activeJob.stage || activeJob.message || "").toLowerCase();
    if (stage.includes("prepar") || stage.includes("load")) return "preparing";
    if (stage.includes("assembl")) return "assembling";
    if (stage.includes("lipsync") || stage.includes("mix") || stage.includes("post")) return "post";
    if (preview) return "live_preview";
    return "processing";
  })();

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const list = await api.listJobs(project.id);
        if (!alive) return;
        setJobs(list);
        const job = list.find(
          (j) => j.scene_id === scene?.id && (j.status === "queued" || j.status === "running")
        );
        if (job && !pauseUpdates) {
          const p = await api.getJobPreview(job.id);
          if (p.preview && (p.preview.sequenceNumber || 0) >= seq) {
            setSeq(p.preview.sequenceNumber || seq);
            setPreview(p.preview);
          }
        }
      } catch {
        /* ignore */
      }
    };
    tick();
    const id = setInterval(tick, 2500);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [project.id, scene?.id, pauseUpdates, seq]);

  useEffect(() => {
    try {
      const es = new EventSource(`/api/projects/${project.id}/preview/stream`);
      esRef.current = es;
      es.onmessage = (ev) => {
        if (pauseUpdates) return;
        try {
          const data = JSON.parse(ev.data);
          if (data.event === "preview_updated" || data.event === "preview_available") {
            const p = data.preview as PreviewPayload;
            if (p?.sceneId && scene?.id && p.sceneId !== scene.id) return;
            if ((p?.sequenceNumber || 0) < seq) return;
            setSeq(p.sequenceNumber || seq);
            setPreview(p);
            if (data.event === "preview_available") {
              setAnnounce(`Live preview is now available for ${scene?.name || "scene"}.`);
            }
          }
        } catch {
          /* ignore */
        }
      };
      return () => {
        es.close();
        esRef.current = null;
      };
    } catch {
      return;
    }
  }, [project.id, scene?.id, pauseUpdates, seq, scene?.name]);

  useEffect(() => {
    return () => {
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };
  }, []);

  const finalSrc = scene?.lipsync_output_path
    ? api.mediaUrl(scene.lipsync_output_path)
    : scene?.output_path
      ? api.mediaUrl(scene.output_path)
      : "";
  const sourceStill = scene?.start_asset_id ? api.assetUrl(scene.start_asset_id) : "";
  const previewSrc = preview?.sourceUrl || (preview?.localPath ? api.mediaUrl(preview.localPath) : "");
  const showDraft = monitorState === "live_preview" || monitorState === "processing" || monitorState === "assembling" || monitorState === "post" || monitorState === "preparing";
  const mediaSrc =
    monitorState === "complete" && finalSrc
      ? finalSrc
      : previewSrc || (showDraft ? sourceStill : finalSrc || sourceStill);

  const aspect = aspectCssValue(scene?.aspect_ratio);

  const capsUnsupported =
    activeJob &&
    String(scene?.engine || "").startsWith("fal_") &&
    !previewSrc;

  return (
    <div className="panel live-preview-monitor">
      <PanelHeading
        title="Director monitor"
        tip="Shows live generation preview when the engine provides intermediates. Otherwise an honest fallback."
      />
      <div className="live-preview-stage" style={{ aspectRatio: aspect }}>
        {mediaSrc ? (
          /\.(mp4|webm|mov)(\?|$)/i.test(mediaSrc) || preview?.mediaType === "video" ? (
            <video
              key={mediaSrc}
              src={mediaSrc}
              controls
              playsInline
              style={{ objectFit: fitMode === "cover" ? "cover" : fitMode === "none" ? "none" : "contain" }}
            />
          ) : (
            <img
              src={mediaSrc}
              alt={showDraft ? "Live generation preview (draft)" : "Scene preview"}
              style={{ objectFit: fitMode === "cover" ? "cover" : fitMode === "none" ? "none" : "contain" }}
            />
          )
        ) : (
          <div className="director-stage-empty">
            <strong>{monitorState === "preparing" ? "Preparing…" : "Idle"}</strong>
            <span>{scene ? scene.name : "Select a scene"}</span>
          </div>
        )}

        {showDraft && !hideOverlay && (
          <div className="live-preview-overlay" aria-live="polite">
            <div className="pill warn">LIVE PREVIEW · Draft quality</div>
            <div>
              {scene?.name} — {scene?.engine}
            </div>
            <div className="scene-meta">
              {activeJob?.stage || activeJob?.message || monitorState} ·{" "}
              {Math.round((activeJob?.progress || 0) * 100)}%
            </div>
            {capsUnsupported && (
              <div className="scene-meta">
                This engine does not provide intermediate preview frames. Storyboard/source remains until final.
              </div>
            )}
          </div>
        )}

        {monitorState === "failed" && (
          <div className="live-preview-overlay bad">
            <strong>Render failed</strong>
            <div className="scene-meta">{activeJob?.message}</div>
            <div className="scene-meta">Latest draft preview preserved when available.</div>
          </div>
        )}
      </div>

      <div className="row-actions" style={{ marginTop: 8 }}>
        <button type="button" className="ghost" onClick={() => setHideOverlay((v) => !v)}>
          {hideOverlay ? "Show Overlay" : "Hide Overlay"}
        </button>
        <button type="button" className="ghost" onClick={() => setPauseUpdates((v) => !v)}>
          {pauseUpdates ? "Resume Updates" : "Pause Preview Updates"}
        </button>
        {activeJob && (activeJob.status === "queued" || activeJob.status === "running") && (
          <button type="button" className="danger" onClick={() => api.cancelJob(activeJob.id)}>
            Cancel Render
          </button>
        )}
        {activeJob && previewSrc && (
          <button
            type="button"
            onClick={async () => {
              await api.savePreviewFrame(activeJob.id, project.id, `${scene?.name || "scene"}_preview`);
              setAnnounce("Preview frame saved to Assets.");
            }}
          >
            Save Preview Frame
          </button>
        )}
      </div>
      {announce && (
        <p className="scene-meta" role="status">
          {announce}
        </p>
      )}
    </div>
  );
}
