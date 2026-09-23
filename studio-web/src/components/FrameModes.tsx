import { useEffect, useMemo, useRef, useState } from "react";
import type { Asset, Project, Scene } from "../types";
import { api } from "../api";
import {
  inferVideoTier,
  inferMinimaxMegapixelTier,
  isMinimaxMegapixelEngine,
  h3DurationDisclosure,
  legalCanvasSize,
} from "../video/legalCanvas";
import { PanelHeading } from "./HelpTip";
import { GpuVramPanel } from "./GpuVramPanel";
import { JobPanel } from "./JobPanel";
import { LivePreviewMonitor, type PreviewChromeState } from "./LivePreviewMonitor";
import { EngineAuthoritySelect } from "./generation/EngineAuthoritySelect";
import { VideoResolutionSelect } from "./generation/VideoResolutionSelect";
import { AspectRatioSelect } from "./generation/AspectRatioSelect";
import { LibraryImagePickerModal } from "./LibraryImagePickerModal";
import {
  extractRenderFailure,
  RenderFailureAlert,
  type RenderFailureInfo,
} from "./RenderFailureAlert";
import { resolveJobOutputVideoAssetId } from "./omniExportToTimeline";

function useLegalVideoCanvas(project: Project, scene: Scene) {
  const engine = String(scene.engine || "auto");
  const aspect = scene.aspect_ratio || "16:9";
  const w = Number(scene.width || project.width || 0);
  const h = Number(scene.height || project.height || 0);
  // MiniMax H3 uses megapixel-labeled tiers ("0.9 MP", …); other engines use
  // the 480p/720p/1080p/2K/4K tiers. The tier type is `string` to carry both.
  const [tier, setTier] = useState<string>(() =>
    isMinimaxMegapixelEngine(engine) ? inferMinimaxMegapixelTier(w, h) : inferVideoTier(w, h),
  );

  useEffect(() => {
    setTier(
      isMinimaxMegapixelEngine(engine) ? inferMinimaxMegapixelTier(w, h) : inferVideoTier(w, h),
    );
  }, [scene.id, engine, w, h]);

  const canvas = useMemo(() => legalCanvasSize(engine, tier, aspect), [engine, tier, aspect]);
  return { engine, aspect, tier, setTier, canvas };
}


function KeyframeSlot({
  label,
  tip,
  assetId,
  images,
  onPick,
  onUpload,
}: {
  label: string;
  tip: string;
  assetId?: string | null;
  images: Asset[];
  onPick: (id: string | null) => void;
  onUpload: (file: File) => void;
}) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const selectedName = useMemo(() => {
    if (!assetId) return null;
    const a = images.find((x) => x.id === assetId);
    return a ? a.tag || a.filename : null;
  }, [assetId, images]);

  return (
    <div className="frame-slot">
      <PanelHeading title={label} tip={tip} as="strong" />
      <div className="frame-slot-preview">
        {assetId ? (
          <img src={api.assetUrl(assetId)} alt={label} />
        ) : (
          <div className="empty">No image</div>
        )}
      </div>
      <div className="row-actions" style={{ marginTop: 8, flexWrap: "wrap", gap: 8 }}>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onUpload(f);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          className="ghost"
          data-testid={`keyframe-upload-button-${label.toLowerCase().replace(/\s+/g, "-")}`}
          onClick={() => fileInputRef.current?.click()}
        >
          Upload
        </button>
        <button
          type="button"
          className="ghost"
          data-testid={`keyframe-library-button-${label.toLowerCase().replace(/\s+/g, "-")}`}
          onClick={() => setPickerOpen(true)}
        >
          Library
        </button>
        {selectedName ? (
          <>
            <span className="muted" style={{ alignSelf: "center" }} title={selectedName}>
              {selectedName.length > 24 ? `${selectedName.slice(0, 23)}…` : selectedName}
            </span>
            <button
              type="button"
              className="ghost"
              aria-label={`Clear ${label}`}
              onClick={() => onPick(null)}
            >
              Clear
            </button>
          </>
        ) : null}
      </div>
      <LibraryImagePickerModal
        images={images}
        currentAssetId={assetId}
        title={`Choose a ${label}`}
        confirmLabel={`Use this ${label.toLowerCase()}`}
        open={pickerOpen}
        onCancel={() => setPickerOpen(false)}
        onPick={(id) => {
          onPick(id);
          setPickerOpen(false);
        }}
      />
    </div>
  );
}


function ExportToTimelineCta({
  project,
  scene,
  sourceSurface,
  placement = "main",
  onDone,
}: {
  project: Project;
  scene: Scene;
  sourceSurface: "one-frame" | "three-frame";
  /** main = preview strip; sidebar = right rail. Distinct testids avoid DOM ambiguity. */
  placement?: "main" | "sidebar";
  onDone: () => void;
}) {
  const testIdBase =
    placement === "sidebar"
      ? `${sourceSurface}-export-to-timeline-sidebar`
      : `${sourceSurface}-export-to-timeline`;
  const [assetId, setAssetId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const refreshExportTarget = async () => {
    try {
      const jobs = await api.listJobs(project.id);
      const sceneJobs = jobs
        .filter((j) => j.scene_id === scene.id && j.status === "done")
        .sort((a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || "")));
      for (const job of sceneJobs) {
        const id = resolveJobOutputVideoAssetId(job);
        if (id) {
          const asset = project.assets.find((a) => a.id === id);
          if (!asset || asset.kind === "video") {
            setAssetId(id);
            return;
          }
        }
      }
      const videos = project.assets
        .filter((a) => a.kind === "video")
        .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
      setAssetId(videos[0]?.id || null);
    } catch {
      setAssetId(null);
    }
  };

  useEffect(() => {
    void refreshExportTarget();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id, scene.id, project.assets.length]);

  if (!assetId) return null;

  return (
    <div
      className="omni-export-to-timeline"
      data-testid={testIdBase}
      style={{ marginTop: 12, display: "1px solid var(--border, #333)", padding: 12, borderRadius: 8 }}
    >
      <strong>Export to Timeline</strong>
      <p className="muted" style={{ margin: "6px 0 10px" }}>
        Send this completed video into Timeline Visual as playable media (no regeneration).
      </p>
      <button
        type="button"
        className="primary"
        data-testid={`${testIdBase}-btn`}
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setErr(null);
          setMsg(null);
          try {
            const res = await api.directorTimelineExportVideoToTimeline(project.id, scene.id, {
              assetId,
              label: `${scene.name || sourceSurface} take`,
              sourceSurface,
            });
            // Paint success before parent refresh remounts this CTA (Wave7 E2E race).
            setMsg(res.message || "Deposited on Timeline Visual.");
            setBusy(false);
            void Promise.resolve().then(() => onDone());
            return;
          } catch (e: any) {
            setErr(String(e?.message || e || "Export failed"));
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Sending..." : "Send video to Timeline (Visual)"}
      </button>
      {msg ? <p className="muted" data-testid={`${testIdBase}-ok`}>{msg}</p> : null}
      {err ? <p className="danger" data-testid={`${testIdBase}-err`}>{err}</p> : null}
    </div>
  );
}

/** 1 Frame — single still → video generation */
export function OneFramePanel({
  project,
  scene,
  onChange,
}: {
  project: Project;
  scene?: Scene;
  onChange: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [genError, setGenError] = useState<RenderFailureInfo | null>(null);
  const [draftPrompt, setDraftPrompt] = useState(scene?.prompt || "");
  const [previewChrome, setPreviewChrome] = useState<PreviewChromeState | null>(null);
  const images = useMemo(() => project.assets.filter((a) => a.kind === "image"), [project.assets]);

  const canvasState = useLegalVideoCanvas(
    project,
    scene ??
      ({
        id: "",
        engine: "auto",
        aspect_ratio: "16:9",
        width: project.width,
        height: project.height,
      } as Scene),
  );

  useEffect(() => {
    setDraftPrompt(scene?.prompt || "");
  }, [scene?.id, scene?.prompt]);

  if (!scene) return <div className="panel"><p className="empty">Select a scene</p></div>;

  const { engine, aspect, tier, setTier, canvas } = canvasState;

  const update = async (patch: Partial<Scene>) => {
    await api.updateScene(project.id, scene.id, { ...scene, ...patch });
    onChange();
  };

  const upload = async (file: File) => {
    const tag = `${scene.name}_frame`.replace(/\s+/g, "_").toLowerCase();
    const asset = (await api.uploadAsset(project.id, file, tag, "image")) as Asset;
    await update({ start_asset_id: asset.id, middle_asset_id: null, end_asset_id: null });
  };

  return (
    <div className="page gen-workspace" data-testid="one-frame-panel">
      <h1>1 Frame</h1>
      <p className="muted">
        One still becomes video. Upload or pick a First Frame, describe the motion, and generate.
      </p>
      {genError && (
        <RenderFailureAlert
          reason={genError.reason}
          technical={genError.technical}
          testId="one-frame-gen-error"
        />
      )}
      <div className="oneframe-layout">
        <div className="oneframe-center">
          <LivePreviewMonitor project={project} scene={scene} inlineActions={false} onChromeStateChange={setPreviewChrome} />
          {previewChrome?.canCancel ? (
            <div className="row" style={{ marginTop: 8 }}>
              <button
                type="button"
                className="danger"
                data-testid="one-frame-cancel-render"
                title="Stop the active render"
                aria-label="Cancel the active render"
                onClick={() => previewChrome.cancelRender()}
              >
                Cancel Render
              </button>
            </div>
          ) : null}
          <ExportToTimelineCta
            project={project}
            scene={scene}
            sourceSurface="one-frame"
            onDone={onChange}
          />

          <div className="frame-slots one">
            <KeyframeSlot
              label="First Frame"
              tip="Opening still for this clip. Upload or select from Library."
              assetId={scene.start_asset_id}
              images={images}
              onPick={(id) => update({ start_asset_id: id, middle_asset_id: null, end_asset_id: null })}
              onUpload={upload}
            />
          </div>

          <div className="field">
            <label htmlFor="one-frame-motion-prompt">Motion prompt</label>
            <textarea
              id="one-frame-motion-prompt"
              data-testid="one-frame-motion-prompt"
              value={draftPrompt}
              onChange={(e) => {
                const next = e.target.value;
                setDraftPrompt(next);
                void update({ prompt: next });
              }}
              placeholder="camera slowly pushes in, soft wind, she turns toward the light…"
            />
          </div>

          <div className="gen-grid">
            <div className="field">
              <label htmlFor="one-frame-engine">Generator</label>
              <EngineAuthoritySelect
                id="one-frame-engine"
                value={(scene.engine as any) || "auto"}
                onChange={(next) => void update({ engine: next })}
                surface="one-frame"
              />
            </div>
            <div className="field">
              <label htmlFor="one-frame-duration">Duration (seconds)</label>
              <input
                id="one-frame-duration"
                type="number"
                min={1}
                max={30}
                step={0.5}
                value={scene.duration_sec}
                onChange={(e) => update({ duration_sec: Number(e.target.value) || 5 })}
              />
              {h3DurationDisclosure(engine, scene.duration_sec, project.fps) ? (
                <p className="scene-meta" data-testid="one-frame-duration-disclosure">
                  {h3DurationDisclosure(engine, scene.duration_sec, project.fps)}
                </p>
              ) : null}
            </div>
            <div className="field">
              <label htmlFor="one-frame-resolution">Resolution</label>
              <VideoResolutionSelect
                id="one-frame-resolution"
                engine={engine}
                aspect={aspect}
                value={tier}
                onChange={(next, width, height) => {
                  setTier(next);
                  void update({ width, height });
                }}
              />
              <p className="muted" data-testid="one-frame-canvas">
                {canvas.available
                  ? `This generator will run ${canvas.width}×${canvas.height}.`
                  : canvas.honestyLabel}
              </p>
            </div>
            <div className="field">
              <label htmlFor="one-frame-aspect">Aspect Ratio</label>
              <AspectRatioSelect
                id="one-frame-aspect"
                value={aspect}
                onChange={(a) => {
                  const next = legalCanvasSize(engine, tier, a);
                  void update({ aspect_ratio: a, width: next.width, height: next.height });
                }}
              />
            </div>
          </div>

          <div className="row-actions">
            <button
              className="primary"
              data-testid="one-frame-generate"
              disabled={busy || !scene.start_asset_id || !canvas.available}
              onClick={async () => {
                if (!canvas.available) {
                  setGenError({
                    reason: canvas.honestyLabel,
                    technical: "Illegal or unavailable canvas was not submitted.",
                  });
                  return;
                }
                setBusy(true);
                setGenError(null);
                try {
                  // MiniMax H3 runs on a 17k+5 frame grid, but the snap is
                  // REQUEST-scoped: the backend builder snaps scene.duration_sec
                  // at generation time and trims the excess. Persist the canvas
                  // only — never write a snapped duration back onto the scene row.
                  await api.updateScene(project.id, scene.id, {
                    ...scene,
                    width: canvas.width,
                    height: canvas.height,
                  });
                  await api.render(project.id, "scene", scene.id, {
                    action_scope: "exploration",
                    engine: scene.engine,
                    width: canvas.width,
                    height: canvas.height,
                    resolution: `${canvas.width}x${canvas.height}`,
                  });
                  onChange();
                } catch (e) {
                  setGenError(await extractRenderFailure(e));
                } finally {
                  setBusy(false);
                }
              }}
            >
              {busy ? "Queuing…" : "Generate from 1 frame"}
            </button>
          </div>
        </div>

        <aside className="oneframe-sidebar" data-testid="one-frame-sidebar">
          <GpuVramPanel
            project={project}
            onChange={onChange}
            compact
            sceneId={scene.id}
            engine={String(scene.engine || "auto")}
            surface="i2v"
            durationSec={scene.duration_sec}
            fps={project.fps}
          />
          <ExportToTimelineCta
            project={project}
            scene={scene}
            sourceSurface="one-frame"
            placement="sidebar"
            onDone={onChange}
          />
          <JobPanel projectId={project.id} onDone={onChange} />
        </aside>
      </div>
    </div>
  );
}

/** 3 Frame — Start / Middle / End keyframe generation */
export function ThreeFramePanel({
  project,
  scene,
  onChange,
}: {
  project: Project;
  scene?: Scene;
  onChange: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [genError, setGenError] = useState<RenderFailureInfo | null>(null);
  const [draftPrompt, setDraftPrompt] = useState(scene?.prompt || "");
  const [previewChrome, setPreviewChrome] = useState<PreviewChromeState | null>(null);
  const images = useMemo(() => project.assets.filter((a) => a.kind === "image"), [project.assets]);

  const canvasState = useLegalVideoCanvas(
    project,
    scene ??
      ({
        id: "",
        engine: "auto",
        aspect_ratio: "16:9",
        width: project.width,
        height: project.height,
      } as Scene),
  );

  useEffect(() => {
    setDraftPrompt(scene?.prompt || "");
  }, [scene?.id, scene?.prompt]);

  if (!scene) return <div className="panel"><p className="empty">Select a scene</p></div>;

  const { engine, aspect, tier, setTier, canvas } = canvasState;

  const update = async (patch: Partial<Scene>) => {
    await api.updateScene(project.id, scene.id, { ...scene, ...patch });
    onChange();
  };

  const uploadSlot = async (role: "start" | "middle" | "end", file: File) => {
    const tag = `${scene.name}_${role}`.replace(/\s+/g, "_").toLowerCase();
    const asset = (await api.uploadAsset(project.id, file, tag, "image")) as Asset;
    const key = `${role}_asset_id` as const;
    await update({ [key]: asset.id } as Partial<Scene>);
  };

  return (
    <div className="page gen-workspace" data-testid="three-frame-panel">
      <h1>3 Frame</h1>
      <p className="muted">
        First and Last stills become video on local MiniMax H3. Middle Frame is optional
        AddGuide. Empty middle keeps the proven first+last graph — ordinary 1F I2V is not 3 Frame.
      </p>
      {genError && (
        <RenderFailureAlert
          reason={genError.reason}
          technical={genError.technical}
          testId="three-frame-gen-error"
        />
      )}
      <div className="threeframe-layout">
        <div className="threeframe-center">
          <LivePreviewMonitor project={project} scene={scene} inlineActions={false} onChromeStateChange={setPreviewChrome} />
          {previewChrome?.canCancel ? (
            <div className="row" style={{ marginTop: 8 }}>
              <button
                type="button"
                className="danger"
                data-testid="three-frame-cancel-render"
                title="Stop the active render"
                aria-label="Cancel the active render"
                onClick={() => previewChrome.cancelRender()}
              >
                Cancel Render
              </button>
            </div>
          ) : null}
          <ExportToTimelineCta
            project={project}
            scene={scene}
            sourceSurface="three-frame"
            onDone={onChange}
          />

          <div className="frame-slots three" data-testid="three-frame-strip">
            <KeyframeSlot
              label="First Frame"
              tip="Opening still. Required."
              assetId={scene.start_asset_id}
              images={images}
              onPick={(id) => update({ start_asset_id: id })}
              onUpload={(f) => uploadSlot("start", f)}
            />
            <KeyframeSlot
              label="Middle Frame (Optional)"
              tip="Mid-clip guidance still. Optional — leave empty for First + Last."
              assetId={scene.middle_asset_id}
              images={images}
              onPick={(id) => update({ middle_asset_id: id })}
              onUpload={(f) => uploadSlot("middle", f)}
            />
            <KeyframeSlot
              label="Last Frame"
              tip="Closing still. Required."
              assetId={scene.end_asset_id}
              images={images}
              onPick={(id) => update({ end_asset_id: id })}
              onUpload={(f) => uploadSlot("end", f)}
            />
          </div>

          <div className="field">
            <label htmlFor="three-frame-motion-prompt">Motion prompt</label>
            <textarea
              id="three-frame-motion-prompt"
              data-testid="three-frame-motion-prompt"
              value={draftPrompt}
              onChange={(e) => {
                const next = e.target.value;
                setDraftPrompt(next);
                void update({ prompt: next });
              }}
              placeholder="walks from door to window, camera follows, rain on glass…"
            />
          </div>

          <div className="gen-grid">
            <div className="field">
              <label htmlFor="three-frame-engine">Generator</label>
              <EngineAuthoritySelect
                id="three-frame-engine"
                value={(scene.engine as any) || "auto"}
                onChange={(next) => void update({ engine: next })}
                surface="three-frame"
              />
            </div>
            <div className="field">
              <label htmlFor="three-frame-duration">Duration (seconds)</label>
              <input
                id="three-frame-duration"
                type="number"
                min={1}
                max={30}
                step={0.5}
                value={scene.duration_sec}
                onChange={(e) => update({ duration_sec: Number(e.target.value) || 5 })}
              />
            </div>
            <div className="field">
              <label htmlFor="three-frame-resolution">Resolution</label>
              <VideoResolutionSelect
                id="three-frame-resolution"
                engine={engine}
                aspect={aspect}
                value={tier}
                onChange={(next, width, height) => {
                  setTier(next);
                  void update({ width, height });
                }}
              />
              <p className="muted" data-testid="three-frame-canvas">
                {canvas.available
                  ? `This generator will run ${canvas.width}×${canvas.height}.`
                  : canvas.honestyLabel}
              </p>
            </div>
            <div className="field">
              <label htmlFor="three-frame-aspect">Aspect Ratio</label>
              <AspectRatioSelect
                id="three-frame-aspect"
                value={aspect}
                onChange={(a) => {
                  const next = legalCanvasSize(engine, tier, a);
                  void update({ aspect_ratio: a, width: next.width, height: next.height });
                }}
              />
            </div>
          </div>

          <div className="row-actions">
            <button
              className="primary"
              data-testid="three-frame-generate"
              // First + Last are required. Middle is optional.
              disabled={busy || !scene.start_asset_id || !scene.end_asset_id || !canvas.available}
              title="Needs First + Last stills on a legal canvas. Middle is optional."
                            onClick={async () => {
                if (!canvas.available) {
                  setGenError({
                    reason: canvas.honestyLabel,
                    technical: "Illegal or unavailable canvas was not submitted.",
                  });
                  return;
                }
                if (!scene.start_asset_id || !scene.end_asset_id) {
                  setGenError({
                    reason: "Add First and Last frames before Generate.",
                    technical: "Middle is optional; First and Last are required.",
                  });
                  return;
                }
                setBusy(true);
                setGenError(null);
                try {
                  // Same rule as 1 Frame: the H3 17k+5 snap is request-scoped
                  // (backend builder snaps + trims). Persist the canvas only;
                  // scene.duration_sec is never mutated by Generate.
                  await api.updateScene(project.id, scene.id, {
                    ...scene,
                    width: canvas.width,
                    height: canvas.height,
                  });
                  await api.render(project.id, "scene", scene.id, {
                    action_scope: "exploration",
                    engine: scene.engine,
                    width: canvas.width,
                    height: canvas.height,
                    resolution: `${canvas.width}x${canvas.height}`,
                  });
                  onChange();
                } catch (e) {
                  setGenError(await extractRenderFailure(e));
                } finally {
                  setBusy(false);
                }
              }}
            >
              {busy ? "Queuing…" : "Generate from 3 frames"}
            </button>
            <p className="muted" data-testid="three-frame-unready">
              First + Last required. Middle optional — empty middle uses the proven local first+last graph (no AddGuide).
            </p>
          </div>
        </div>

        <aside className="threeframe-sidebar" data-testid="three-frame-sidebar">
          <GpuVramPanel
            project={project}
            onChange={onChange}
            compact
            sceneId={scene.id}
            engine={String(scene.engine || "auto")}
            surface="multiFrame"
            durationSec={scene.duration_sec}
            fps={project.fps}
          />
          <ExportToTimelineCta
            project={project}
            scene={scene}
            sourceSurface="three-frame"
            placement="sidebar"
            onDone={onChange}
          />
          <JobPanel projectId={project.id} onDone={onChange} />
        </aside>
      </div>
    </div>
  );
}
