import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { shouldSuspendDependentPolling } from "../runtime/studioApiConnection";
import type { EngineName, Job, Project } from "../types";
import {
  clearPersistedTxt2VidPreviewAssetId,
  extractTxt2VidOutputAssetId,
  latestSuccessfulTxt2VidAssetId,
  persistTxt2VidPreviewAssetId,
  readPersistedTxt2VidPreviewAssetId,
  resolveTxt2VidPreviewAsset,
} from "./txt2vidPreview";
import {
  FPS_OPTIONS,
  STYLE_PRESETS,
  type EditorTab,
} from "../workspacePrefs";
import {
  durationFidelityMessage,
  inferMinimaxMegapixelTier,
  inferVideoTier,
  isMinimaxMegapixelEngine,
  isMinimaxMegapixelTier,
  legalCanvasSize,
  normalizeVideoTier,
} from "../video/legalCanvas";
import { JobPanel } from "./JobPanel";
import { GpuVramPanel } from "./GpuVramPanel";
import {
  extractRenderFailure,
  RenderFailureAlert,
  splitFailureMessage,
  type RenderFailureInfo,
} from "./RenderFailureAlert";
import { LivePreviewMonitor } from "./LivePreviewMonitor";
import { PaidFalFallbackDialog } from "./PaidFalFallbackDialog";
import { EngineAuthoritySelect, ENGINE_NAME_TO_PRODUCT } from "./generation/EngineAuthoritySelect";
import { VideoResolutionSelect } from "./generation/VideoResolutionSelect";
import { AspectRatioSelect } from "./generation/AspectRatioSelect";
import { T2V_ENGINE_NAMES } from "./generation/engineSurfacePolicy";
import { useTimelineVideoGenerators } from "../timelineMaster/useTimelineVideoGenerators";
import { resolveGeneratorOption } from "../timelineMaster/draftCapabilities";

const FAL_ENGINES = new Set<string>([
  "seedance-2.0",
  "seedance-2.5",
  "fal_seedance",
  "fal_kling",
  "fal_veo",
  "fal_runway",
]);

const NO_T2V_BLOCKER =
  "No executable Text-to-Video engine right now. Install LTX 2.5 or MiniMax H3 in Source Manager, or connect a hosted generator in Setup.";

function projectDefaults(project: Project): Record<string, any> {
  try {
    return project.defaults_json ? JSON.parse(project.defaults_json) : {};
  } catch {
    return {};
  }
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
  const d = projectDefaults(project);
  const [prompt, setPrompt] = useState("");
  const [negative, setNegative] = useState(project.negative_prompt);
  const [style, setStyle] = useState(String(d.prompt_style || STYLE_PRESETS[0]));
  const [aspect, setAspect] = useState(String(d.aspect || "16:9"));
  const [fps, setFps] = useState<string>(String(d.fps ?? "auto"));
  const [duration, setDuration] = useState(5);
  const [engine, setEngine] = useState<string>(() => {
    const initial = String(d.engine || "auto");
    if (initial === "auto" || (T2V_ENGINE_NAMES as readonly string[]).includes(initial)) return initial;
    return "auto";
  });
  const [resolution, setResolution] = useState<string>(() => {
    const r = String(d.resolution || "720p");
    // Keep MiniMax megapixel labels as-is; normalize legacy labels for the
    // 480p/720p/1080p/2K/4K tier dropdown used by other engines.
    return isMinimaxMegapixelTier(r) ? r : normalizeVideoTier(r);
  });
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
  const [renderFailure, setRenderFailure] = useState<RenderFailureInfo | null>(null);
  const [outputAssetId, setOutputAssetId] = useState<string | null>(() =>
    readPersistedTxt2VidPreviewAssetId(project.id),
  );
  const [fallbackOpen, setFallbackOpen] = useState(false);
  const [fallbackMessage, setFallbackMessage] = useState("");
  const [fallbackEngine, setFallbackEngine] = useState<string>("");

  const size = useMemo(
    () => legalCanvasSize(engine, resolution, aspect),
    [engine, resolution, aspect],
  );
  const previewAsset = useMemo(
    () => resolveTxt2VidPreviewAsset(project.id, project.assets || [], outputAssetId),
    [project.id, project.assets, outputAssetId],
  );

  useEffect(() => {
    const persisted = readPersistedTxt2VidPreviewAssetId(project.id);
    setOutputAssetId(persisted);
    if (persisted) return;
    let alive = true;
    api
      .listJobs(project.id)
      .then((jobs) => {
        if (!alive) return;
        const recovered = latestSuccessfulTxt2VidAssetId(jobs);
        if (!recovered) return;
        setOutputAssetId(recovered);
        persistTxt2VidPreviewAssetId(project.id, recovered);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [project.id]);

  // When the engine switches to/from MiniMax H3, translate the resolution
  // label between the 480p/720p/… tier set and the MiniMax megapixel set so the
  // dropdown always shows a valid selected option and `size` stays consistent.
  useEffect(() => {
    if (isMinimaxMegapixelEngine(engine)) {
      if (!isMinimaxMegapixelTier(resolution)) {
        setResolution(inferMinimaxMegapixelTier(size.width, size.height));
      }
    } else if (isMinimaxMegapixelTier(resolution)) {
      setResolution(inferVideoTier(size.width, size.height));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [engine]);

  // HONESTY: a real executable T2V engine is one that can generate video from
  // text alone (no start frame) AND is executable at runtime (credentials ready).
  const videoOptions = useTimelineVideoGenerators();
  const executableT2vEngine = (T2V_ENGINE_NAMES as readonly string[]).find((eng) => {
    const productId = ENGINE_NAME_TO_PRODUCT[eng as EngineName] || "";
    const opt = resolveGeneratorOption(videoOptions, productId, eng);
    return Boolean(opt?.executable);
  });
  const noExecutableT2v = !executableT2vEngine;

  const fpsNumber = Number(fps) || 24;
  const durationBlock = durationFidelityMessage(engine, duration, fpsNumber);
  const vramWarn = useMemo(() => {
    const pixels = size.width * size.height;
    if (project.vram_gb < 16 && (resolution === "4K" || duration > 8)) {
      return "VRAM planner: 4K / long duration may exceed local capacity — prefer a shorter clip.";
    }
    if (project.vram_gb < 24 && pixels > 1920 * 1080) {
      return "VRAM planner: oversized combo — lower resolution or use shorter duration.";
    }
    return null;
  }, [size, resolution, duration, project.vram_gb]);

  useEffect(() => {
    if (!job || job.status === "done" || job.status === "failed" || job.status === "cancelled") return;
    const t = setInterval(() => {
      if (shouldSuspendDependentPolling()) return;
      api.getJob(job.id).then((j) => {
        setJob(j);
        if (j.status === "failed") {
          setRenderFailure(splitFailureMessage(j.message || "Generation failed."));
          setMsg(null);
        }
        if (j.status === "cancelled") {
          setMsg("Render cancelled.");
        }
        if (j.status === "done") {
          const assetId = extractTxt2VidOutputAssetId(j);
          if (assetId) {
            setOutputAssetId(assetId);
            persistTxt2VidPreviewAssetId(project.id, assetId);
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

  // Resolve the effective T2V engine. AUTO → first executable T2V (never local I2V).
  const resolveEffectiveEngine = (): string | null => {
    if (engine !== "auto") {
      const productId = ENGINE_NAME_TO_PRODUCT[engine as EngineName] || "";
      const opt = resolveGeneratorOption(videoOptions, productId, engine);
      return opt?.executable ? engine : null;
    }
    return executableT2vEngine ?? null;
  };

  // Submit a CLEAN TEXT-ONLY payload. No references, no spatial maps, no start
  // frame, no scene-reference provenance. Text to Video is text-only.
  const queueTxt2Vid = async (opts: { engine: string; paidFallbackApproved?: boolean }) => {
    setBusy(true);
    setMsg(null);
    setRenderFailure(null);
    try {
      const nextHist = [prompt, ...history.filter((h) => h !== prompt)].slice(0, 20);
      setHistory(nextHist);
      localStorage.setItem("adept_txt2vid_history", JSON.stringify(nextHist));
      const j = await api.txt2vid(project.id, {
        prompt,
        negative,
        style,
        aspect,
        fps,
        duration_sec: duration,
        engine: opts.engine,
        width: size.width,
        height: size.height,
        resolution,
        providerPreference: FAL_ENGINES.has(opts.engine) ? "fal" : "local",
        paidFallbackApproved: Boolean(opts.paidFallbackApproved),
      });
      setJob(j as Job);
    } catch (e: unknown) {
      setRenderFailure(await extractRenderFailure(e));
      setMsg(null);
    } finally {
      setBusy(false);
    }
  };

  const generate = async () => {
    if (!prompt.trim()) return;
    if (!size.available) {
      setMsg(size.honestyLabel || "This resolution is not legal for the selected generator.");
      return;
    }
    const effective = resolveEffectiveEngine();
    if (!effective) {
      // HONEST BLOCKER: no executable T2V path. No submit, no I2V fallback,
      // no silent fal. Surface the exact runtime/provider blocker.
      setMsg(NO_T2V_BLOCKER);
      return;
    }
    if (FAL_ENGINES.has(effective)) {
      setFallbackMessage(
        `Engine ${effective} bills through fal.ai. This is a true Text-to-Video cloud submission. Approve only if you intend a paid cloud generation.`,
      );
      setFallbackEngine(effective);
      setFallbackOpen(true);
      return;
    }
    await queueTxt2Vid({ engine: effective });
  };

  const onFallbackAction = async (action: "cancel" | "approve_paid_fal") => {
    setFallbackOpen(false);
    if (action === "cancel") {
      setMsg("Cancelled — no fal.ai request submitted.");
      return;
    }
    if (action === "approve_paid_fal") {
      await queueTxt2Vid({ engine: fallbackEngine, paidFallbackApproved: true });
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
      <h1>Text to Video</h1>
      <p className="muted">
        Text-to-video. Describe a shot and generate video from words alone — no
        start picture. Local LTX 2.5 and MiniMax H3 run here. 1 Frame and 3 Frame
        need a still. Timeline uses character and place references.{" "}
        {noExecutableT2v
          ? "Install LTX 2.5 or MiniMax H3, or connect a hosted generator in Setup."
          : "Local generators run on this computer. Hosted generators need your approval before they bill."}
      </p>
      {noExecutableT2v && (
        <p className="pill warn" data-testid="txt2vid-no-t2v">
          {NO_T2V_BLOCKER}
        </p>
      )}
      {vramWarn && <p className="pill warn">{vramWarn}</p>}
      {renderFailure && (
        <RenderFailureAlert
          reason={renderFailure.reason}
          technical={renderFailure.technical}
          testId="txt2vid-message"
        />
      )}
      {!renderFailure && msg && (
        <p className="pill warn" data-testid="txt2vid-message">
          {msg}
        </p>
      )}

      <div className="txt2vid-layout">
        <div className="txt2vid-center">
          <LivePreviewMonitor
            project={project}
            inlineActions={false}
            libraryAsset={previewAsset}
            idleDetail="Finished videos play here. Generate a shot, then press play."
            onClearLibraryAsset={
              previewAsset
                ? () => {
                    setOutputAssetId(null);
                    clearPersistedTxt2VidPreviewAssetId(project.id);
                  }
                : undefined
            }
          />
          {job && (job.status === "queued" || job.status === "running" || job.status === "cancelling") ? (
            <div className="row" style={{ marginTop: 8 }}>
              <button
                type="button"
                className="danger"
                data-testid="txt2vid-cancel-render"
                title="Stop the active render"
                aria-label="Cancel the active render"
                disabled={job.status === "cancelling"}
                onClick={async () => {
                  try {
                    await api.cancelJob(job.id);
                    setMsg("Cancel requested — waiting for the runtime to stop.");
                  } catch (e: unknown) {
                    setMsg(e instanceof Error ? e.message : "Cancel request failed.");
                  }
                }}
              >
                {job.status === "cancelling" ? "Cancelling…" : "Cancel Render"}
              </button>
            </div>
          ) : null}

          <div className="field">
            <label htmlFor="txt2vid-prompt">Prompt</label>
            <textarea
              id="txt2vid-prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={5}
              placeholder="Describe the shot — a cinematic text-to-video prompt."
            />
          </div>

          <div className="gen-grid">
        <div className="field">
          <label htmlFor="txt2vid-engine">Generator</label>
          <EngineAuthoritySelect
            id="txt2vid-engine"
            value={engine}
            onChange={(next) => setEngine(next)}
            requireTextToVideo
          />
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
          {durationBlock ? <p className="scene-meta">{durationBlock}</p> : null}
        </div>
        <div className="field">
          <label htmlFor="txt2vid-aspect">Aspect Ratio</label>
          <AspectRatioSelect
            id="txt2vid-aspect"
            value={aspect}
            onChange={(a) => setAspect(a)}
          />
        </div>
        <div className="field">
          <label htmlFor="txt2vid-resolution">Resolution</label>
          <VideoResolutionSelect
            id="txt2vid-resolution"
            engine={engine}
            aspect={aspect}
            value={resolution}
            onChange={(next) => setResolution(next)}
          />
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
        <div className="field">
          <label htmlFor="txt2vid-negative">Negative</label>
          <textarea
            id="txt2vid-negative"
            value={negative}
            onChange={(e) => setNegative(e.target.value)}
            rows={2}
          />
        </div>
      </div>

      <div className="row" style={{ marginTop: "1rem" }}>
        <button
          type="button"
          className="primary"
          data-testid="txt2vid-generate"
          disabled={busy || !prompt.trim() || Boolean(durationBlock)}
          onClick={generate}
        >
          {busy ? "Queuing…" : "Generate Video"}
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

        </div>

        <aside className="txt2vid-sidebar" data-testid="txt2vid-sidebar">
          <GpuVramPanel
            project={project}
            onChange={() => void onChange()}
            compact
            engine={engine}
            surface="t2v"
            aspect={aspect}
            durationSec={duration}
            fps={Number(fps) || project.fps || 24}
          />
          <JobPanel projectId={project.id} onDone={() => void onChange()} />
        </aside>
      </div>

      <PaidFalFallbackDialog
        open={fallbackOpen}
        title="Approve paid Text-to-Video"
        message={fallbackMessage}
        onAction={onFallbackAction}
      />
    </div>
  );
}
