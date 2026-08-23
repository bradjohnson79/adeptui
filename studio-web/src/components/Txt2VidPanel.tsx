import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api";
import { shouldSuspendDependentPolling } from "../runtime/studioApiConnection";
import type { Job, Project } from "../types";
import {
  ASPECT_PRESETS,
  FPS_OPTIONS,
  STYLE_PRESETS,
  resolutionToSize,
  type EditorTab,
} from "../workspacePrefs";
import { JobPanel } from "./JobPanel";
import { PaidFalFallbackDialog, type PaidFalFallbackAction } from "./PaidFalFallbackDialog";
import { ReferencesPane } from "./sceneReferences/ReferencesPane";
import { PromptIntelligencePanel } from "./CoDirector/PromptIntelligencePanel";
import { SpatialReferenceFieldset } from "./spatial-map/SpatialReferenceFieldset";
import { buildAiGuidedSetupPath } from "../setup/navigation";
import { MiniMaxH3PlanPanel } from "./minimax-h3/MiniMaxH3PlanPanel";

function projectDefaults(project: Project): Record<string, any> {
  try {
    return project.defaults_json ? JSON.parse(project.defaults_json) : {};
  } catch {
    return {};
  }
}

function parseLocalStartFrameBlocker(err: unknown): { code?: string; message: string } | null {
  const message = err instanceof Error ? err.message : String(err);
  try {
    const parsed = JSON.parse(message);
    if (parsed && typeof parsed === "object" && parsed.code === "LOCAL_START_FRAME_REQUIRED") {
      return { code: parsed.code, message: String(parsed.message || message) };
    }
  } catch {
    /* not JSON */
  }
  if (err instanceof ApiError && err.code === "LOCAL_START_FRAME_REQUIRED") {
    return { code: err.code, message: err.message };
  }
  if (/start frame|LOCAL_START_FRAME_REQUIRED|image-to-video/i.test(message)) {
    return { code: "LOCAL_START_FRAME_REQUIRED", message };
  }
  return null;
}

export function Txt2VidPanel({
  project,
  onChange,
  onGo,
}: {
  project: Project;
  onChange: () => Promise<void>;
  onGo: (tab: EditorTab) => void;
}) {
  const openVideoSetup = (componentId?: string) => {
    window.location.assign(
      buildAiGuidedSetupPath({
        projectId: project.id,
        componentId,
        source: "video_studio",
      }),
    );
  };
  const d = projectDefaults(project);
  const [prompt, setPrompt] = useState("");
  const [negative, setNegative] = useState(project.negative_prompt);
  const [style, setStyle] = useState(String(d.prompt_style || STYLE_PRESETS[0]));
  const [aspect, setAspect] = useState(String(d.aspect || "16:9"));
  const [fps, setFps] = useState<string>(String(d.fps ?? "auto"));
  const [duration, setDuration] = useState(5);
  const [engine, setEngine] = useState(String(d.engine || "auto"));
  const [resolution, setResolution] = useState(String(d.resolution || "720p"));
  const [history, setHistory] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem("adept_txt2vid_history") || "[]");
    } catch {
      return [];
    }
  });
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [tip, setTip] = useState<string | null>(null);
  const [outputAssetId, setOutputAssetId] = useState<string | null>(null);
  const [fallbackOpen, setFallbackOpen] = useState(false);
  const [fallbackMessage, setFallbackMessage] = useState("");
  const [spatialMapId, setSpatialMapId] = useState<string | undefined>();
  const [spatialMapVersion, setSpatialMapVersion] = useState<string | undefined>();
  const [spatialStartCameraId, setSpatialStartCameraId] = useState<string | undefined>();
  const [spatialEndCameraId, setSpatialEndCameraId] = useState<string | undefined>();

  const size = useMemo(() => resolutionToSize(resolution, aspect), [resolution, aspect]);
  const localI2vSelected =
    engine === "auto" || engine === "ltx" || engine === "wan";
  const hunyuanSelected = engine === "hunyuan15" || engine === "hunyuan13b";

  const vramWarn = useMemo(() => {
    const pixels = size.width * size.height;
    if (project.vram_gb < 16 && (resolution === "4K" || duration > 8)) {
      return "VRAM planner: 4K / long duration may exceed local capacity — prefer a shorter local I2V clip.";
    }
    if (project.vram_gb < 24 && pixels > 1920 * 1080) {
      return "VRAM planner: oversized combo for local engines — lower resolution or use shorter duration.";
    }
    return null;
  }, [size, resolution, duration, project.vram_gb]);

  useEffect(() => {
    const low = prompt.toLowerCase();
    if (/\b(character|person|hero|girl|boy|man|woman)\b/.test(low) && !/@/.test(prompt)) {
      setTip("Tip: create a Character Profile and reference with @profile — never auto-applied.");
    } else if (/\b(pan|dolly|orbit|crane|tracking)\b/.test(low)) {
      setTip("Tip: Director Camera Motion can encode intentional moves after promote.");
    } else {
      setTip(null);
    }
  }, [prompt]);

  useEffect(() => {
    if (!job || job.status === "done" || job.status === "failed" || job.status === "cancelled") return;
    const t = setInterval(() => {
      if (shouldSuspendDependentPolling()) return;
      api.getJob(job.id).then((j) => {
        setJob(j);
        if (j.status === "failed") {
          const blocker = parseLocalStartFrameBlocker({ message: j.message } as Error);
          if (blocker || /LOCAL_START_FRAME_REQUIRED|start frame|PAID_FAL_APPROVAL/i.test(j.message || "")) {
            setFallbackMessage(
              j.message ||
                "Local engine requires a start frame. Generate a local still first, or approve a paid Hosted AI Provider path.",
            );
            setFallbackOpen(true);
          }
        }
        if (j.status === "done") {
          try {
            const p = JSON.parse(j.params_json || "{}");
            if (p.output_asset_id) setOutputAssetId(p.output_asset_id);
          } catch {
            /* ignore */
          }
          onChange();
          api
            .getLearning(project.id)
            .then((state) => {
              const items = [...(state.items || [])];
              const notes = [
                { category: "prompts", text: `Preferred Txt2Vid prompt length ~${prompt.split(/\s+/).length} words` },
                { category: "engines", text: `Txt2Vid engine preference: ${engine}` },
                { category: "pacing", text: `Txt2Vid duration preference: ${duration}s` },
                { category: "render", text: `Txt2Vid aspect ${aspect} @ ${resolution}` },
              ];
              for (const n of notes) {
                if (!items.some((i: any) => i.text === n.text)) {
                  items.push({ id: crypto.randomUUID(), ...n, enabled: true });
                }
              }
              return api.putLearning(project.id, { ...state, items });
            })
            .catch(() => undefined);
        }
      });
    }, 1500);
    return () => clearInterval(t);
  }, [job, onChange, project.id, prompt, engine, duration, aspect, resolution]);

  const queueTxt2Vid = async (opts?: { paidFallbackApproved?: boolean }) => {
    setBusy(true);
    setMsg(null);
    try {
      const nextHist = [prompt, ...history.filter((h) => h !== prompt)].slice(0, 20);
      setHistory(nextHist);
      localStorage.setItem("adept_txt2vid_history", JSON.stringify(nextHist));
      const sceneId = project.scenes[0]?.id;
      let referenceProvenance: Record<string, unknown> | undefined;
      if (sceneId) {
        try {
          const pf = await api.sceneReferences.preflight(project.id, {
            scope_type: "scene",
            scope_id: sceneId,
            workflow_key: "text_to_video",
          });
          referenceProvenance = (pf.provenance as Record<string, unknown>) || undefined;
        } catch {
          referenceProvenance = undefined;
        }
      }
      const spatialReferenceBundle =
        spatialMapId
          ? (
              await api.spatialMap.referenceBundle(
                project.id,
                spatialMapId,
                "video",
                spatialStartCameraId || undefined
              )
            ).bundle
          : undefined;
      const j = await api.txt2vid(project.id, {
        prompt,
        negative,
        style,
        aspect,
        fps,
        duration_sec: duration,
        engine,
        width: size.width,
        height: size.height,
        resolution,
        providerPreference: "local",
        paidFallbackApproved: Boolean(opts?.paidFallbackApproved),
        sceneReferenceProvenance: referenceProvenance,
        spatialMapId,
        spatialMapVersion,
        spatialStartCameraId,
        spatialEndCameraId,
        spatialReferenceBundle,
      });
      setJob(j as Job);
    } catch (e: any) {
      const blocker = parseLocalStartFrameBlocker(e);
      if (blocker) {
        setFallbackMessage(blocker.message);
        setFallbackOpen(true);
        setMsg(blocker.message);
      } else {
        setMsg(e?.message || String(e));
      }
    } finally {
      setBusy(false);
    }
  };

  const generate = async () => {
    // LOCAL-16: local-first without a start frame → explain + preferred local still action.
    if (localI2vSelected) {
      setFallbackMessage(
        "The chosen local engine (LTX / WAN) requires a start frame. Generate a local start frame and continue — fal.ai is optional paid fallback only.",
      );
      setFallbackOpen(true);
      return;
    }
    // Explicit fal engine: still require visible paid approval (never silent).
    setFallbackMessage(
      `Engine ${engine} bills through fal.ai. Prefer generating a local start frame + LTX when possible. Approve only if you intend a paid cloud submission.`,
    );
    setFallbackOpen(true);
  };

  const onFallbackAction = async (action: PaidFalFallbackAction) => {
    setFallbackOpen(false);
    if (action === "cancel") {
      setMsg("Cancelled — no fal.ai request submitted.");
      return;
    }
    if (action === "generate_local_start_frame") {
      onGo("imagegen");
      setMsg("Open ImageGen to create a local start frame, then render the scene with LTX.");
      return;
    }
    if (action === "approve_paid_fal") {
      await queueTxt2Vid({ paidFallbackApproved: true });
    }
  };

  const promote = async (target: string) => {
    if (!outputAssetId) {
      setMsg("Wait for generation to finish (asset id).");
      return;
    }
    await api.promote(project.id, { asset_id: outputAssetId, target });
    await onChange();
    setMsg(`Promoted → ${target}`);
  };

  return (
    <div className="page gen-workspace" data-testid="txt2vid-panel">
      <h1>Txt2Vid</h1>
      <p className="muted">
        Local-first text-to-video. Local LTX/WAN need a start frame — Studio offers local still
        generation before any paid fal.ai path.
      </p>
      {vramWarn && <p className="pill warn">{vramWarn}</p>}
      {tip && <p className="pill">{tip}</p>}
      {msg && (
        <p className="pill warn" data-testid="txt2vid-message">
          {msg}
        </p>
      )}

      <ReferencesPane
        project={project}
        sceneId={project.scenes[0]?.id || null}
        workflowTab="txt2vid"
        onChange={() => void onChange()}
      />

      <SpatialReferenceFieldset
        projectId={project.id}
        value={{ spatialMapId, spatialMapVersion, spatialStartCameraId, spatialEndCameraId }}
        onChange={(patch) => {
          if ("spatialMapId" in patch) setSpatialMapId(patch.spatialMapId);
          if ("spatialMapVersion" in patch) setSpatialMapVersion(patch.spatialMapVersion);
          if ("spatialStartCameraId" in patch) setSpatialStartCameraId(patch.spatialStartCameraId);
          if ("spatialEndCameraId" in patch) setSpatialEndCameraId(patch.spatialEndCameraId);
        }}
        showMotionCameras
        testIdPrefix="video"
      />

      <div className="field">
        <label htmlFor="txt2vid-prompt">Prompt (@profile · #motion)</label>
        <textarea
          id="txt2vid-prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={4}
        />
      </div>
      <PromptIntelligencePanel
        creatorPrompt={prompt}
        domain="video"
        engineId={engine}
        projectId={project.id}
        negativePrompt={negative}
        compact
        onApply={({ finalProviderPrompt }) => setPrompt(finalProviderPrompt)}
      />
      <div className="field">
        <label htmlFor="txt2vid-negative">Negative</label>
        <textarea
          id="txt2vid-negative"
          value={negative}
          onChange={(e) => setNegative(e.target.value)}
          rows={2}
        />
      </div>
      <div className="field">
        <label htmlFor="txt2vid-history">History</label>
        <select
          id="txt2vid-history"
          value=""
          onChange={(e) => {
            if (e.target.value) setPrompt(e.target.value);
          }}
        >
          <option value="">Load previous…</option>
          {history.map((h) => (
            <option key={h} value={h}>
              {h.slice(0, 80)}
            </option>
          ))}
        </select>
      </div>

      <div className="gen-grid">
        <div className="field">
          <label htmlFor="txt2vid-style">Style</label>
          <select id="txt2vid-style" value={style} onChange={(e) => setStyle(e.target.value)}>
            {STYLE_PRESETS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="txt2vid-aspect">Aspect</label>
          <select id="txt2vid-aspect" value={aspect} onChange={(e) => setAspect(e.target.value)}>
            {ASPECT_PRESETS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="txt2vid-fps">FPS</label>
          <select id="txt2vid-fps" value={fps} onChange={(e) => setFps(e.target.value)}>
            {FPS_OPTIONS.map((f) => (
              <option key={String(f)} value={String(f)}>
                {f}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="txt2vid-duration">Duration (s)</label>
          <input
            id="txt2vid-duration"
            type="number"
            min={2}
            max={30}
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value))}
          />
        </div>
        <div className="field">
          <label htmlFor="txt2vid-engine">Engine</label>
          <select id="txt2vid-engine" value={engine} onChange={(e) => setEngine(e.target.value)}>
            {[
              ["auto", "Auto"],
              ["minimax-h3", "MiniMax H3 (Default)"],
              ["ltx", "LTX 2.5"],
              ["minimax-h3", "MiniMax H3"],
              ["hunyuan15", "HunyuanVideo 1.5"],
              ["hunyuan13b", "HunyuanVideo 13B"],
              ["wan", "WAN 2.2 (Optional)"],
              ["fal_seedance", "fal_seedance"],
              ["fal_veo", "fal_veo"],
              ["fal_kling", "fal_kling"],
              ["fal_runway", "fal_runway"],
            ].map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="txt2vid-resolution">Resolution</label>
          <select
            id="txt2vid-resolution"
            value={resolution}
            onChange={(e) => setResolution(e.target.value)}
          >
            {["720p", "1080p", "1440p", "4K"].map((r) => (
              <option key={r} value={r}>
                {r} ({resolutionToSize(r, aspect).width}×{resolutionToSize(r, aspect).height})
              </option>
            ))}
          </select>
        </div>
      </div>

      {localI2vSelected && (
        <div className="card" style={{ marginTop: "0.75rem" }} data-testid="local-start-frame-hint">
          <strong>Local-first path</strong>
          <p className="muted">
            No start frame yet → generate a local still (preferred), bind it, then render with LTX
            Video (default). Paid fal.ai is never submitted without approval.
          </p>
          <button type="button" onClick={() => onGo("imagegen")}>
            Open ImageGen
          </button>
        </div>
      )}
      {hunyuanSelected && (
        <div className="card" style={{ marginTop: "0.75rem" }} data-testid="hunyuan-t2v-hint">
          <strong>Hunyuan local path</strong>
          <p className="muted">
            True local Text-to-Video is available only after this Hunyuan provider is installed and
            certified. Until then, use Image-to-Video with a start frame, or keep LTX as default.
          </p>
          <button type="button" onClick={() => openVideoSetup("hunyuan_video_13b")}>
            Open Video Model Library
          </button>
        </div>
      )}
      {engine === "minimax-h3" ? (
        <MiniMaxH3PlanPanel
          projectId={project.id}
          prompt={prompt}
          mode="text-to-video"
          sourceSurface="text-to-video"
          durationSec={duration}
        />
      ) : null}

      <div className="row" style={{ marginTop: "1rem" }}>
        <button
          type="button"
          className="primary"
          data-testid="txt2vid-generate"
          disabled={busy || !prompt.trim()}
          onClick={generate}
        >
          {busy ? "Queuing…" : "Generate"}
        </button>
      </div>

      {job && (
        <p className="scene-meta" style={{ marginTop: "0.75rem" }}>
          Job {job.status} · {Math.round((job.progress || 0) * 100)}% — {job.message}
        </p>
      )}

      {job?.status === "done" && (
        <div className="promote-bar">
          <h3>Promote</h3>
          <div className="row" style={{ flexWrap: "wrap", gap: "0.4rem" }}>
            <button type="button" onClick={() => promote("scene_new")}>
              Add to Director as Scene
            </button>
            <button
              type="button"
              onClick={() =>
                api
                  .promote(project.id, {
                    asset_id: outputAssetId,
                    target: "scene_start",
                    scene_id: project.scenes[0]?.id,
                  })
                  .then(onChange)
              }
            >
              Start
            </button>
            <button
              type="button"
              onClick={() =>
                api
                  .promote(project.id, {
                    asset_id: outputAssetId,
                    target: "scene_middle",
                    scene_id: project.scenes[0]?.id,
                  })
                  .then(onChange)
              }
            >
              Middle
            </button>
            <button
              type="button"
              onClick={() =>
                api
                  .promote(project.id, {
                    asset_id: outputAssetId,
                    target: "scene_end",
                    scene_id: project.scenes[0]?.id,
                  })
                  .then(onChange)
              }
            >
              End
            </button>
            <button type="button" onClick={() => promote("profile")}>
              Save to Profiles
            </button>
            <button type="button" onClick={() => onGo("timeline")}>
              Open Timeline
            </button>
          </div>
        </div>
      )}

      <div style={{ marginTop: "1.25rem" }}>
        <JobPanel projectId={project.id} onDone={() => void onChange()} />
      </div>

      <PaidFalFallbackDialog
        open={fallbackOpen}
        message={fallbackMessage}
        onAction={onFallbackAction}
      />
    </div>
  );
}
