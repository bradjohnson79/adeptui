import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Job, Project } from "../types";
import {
  ASPECT_PRESETS,
  IMAGE_STYLE_PRESETS,
  resolutionToSize,
  type EditorTab,
} from "../workspacePrefs";
import { LoRAManager } from "./LoRAManager";
import { JobPanel } from "./JobPanel";

const REF_ROLES = [
  "character",
  "face",
  "clothing",
  "pose",
  "env",
  "prop",
  "lighting",
  "composition",
  "style",
] as const;

const EDIT_OPS = [
  "inpaint",
  "outpaint",
  "bg_remove",
  "relight",
  "upscale",
  "object_replace",
  "face_refine",
  "grade",
  "style_transfer",
  "consistency",
] as const;

function projectDefaults(project: Project): Record<string, any> {
  try {
    return project.defaults_json ? JSON.parse(project.defaults_json) : {};
  } catch {
    return {};
  }
}

export function ImageGenPanel({
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
  const [style, setStyle] = useState(IMAGE_STYLE_PRESETS[0]);
  const [aspect, setAspect] = useState(String(d.aspect || "1:1"));
  const [resolution, setResolution] = useState("1080p");
  const [model, setModel] = useState(String(d.imagegen_model || "auto"));
  const [models, setModels] = useState<{ id: string; label: string }[]>([]);
  const [refs, setRefs] = useState<{ assetId: string; role: string }[]>([]);
  const [loraOpen, setLoraOpen] = useState(false);
  const [loraStack, setLoraStack] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [outputAssetId, setOutputAssetId] = useState<string | null>(null);
  const [reasons, setReasons] = useState<string[]>([]);
  const [history, setHistory] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem("adept_imagegen_history") || "[]");
    } catch {
      return [];
    }
  });

  const size = useMemo(() => resolutionToSize(resolution, aspect === "custom" ? "1:1" : aspect), [resolution, aspect]);

  useEffect(() => {
    api.imagegenModels().then(setModels).catch(() => setModels([]));
    api.loraStack(`project:${project.id}`).then((r) => setLoraStack(r.stack || [])).catch(() => undefined);
  }, [project.id]);

  useEffect(() => {
    const r: string[] = [];
    if (model === "auto") r.push("Auto → FLUX-family default (then HiDream → SD3.5 → Custom)");
    if (refs.length) r.push(`${refs.length} reference(s) attached — prefer models that honor refs when available`);
    if (style) r.push(`Style: ${style}`);
    if (project.vram_gb < 16 && resolution === "4K") r.push("VRAM: 4K may be heavy — consider 1080p");
    setReasons(r);
  }, [model, refs, style, resolution, project.vram_gb]);

  useEffect(() => {
    if (!job || job.status === "done" || job.status === "failed" || job.status === "cancelled") return;
    const t = setInterval(() => {
      api.getJob(job.id).then((j) => {
        setJob(j);
        if (j.status === "done") {
          try {
            const p = JSON.parse(j.params_json || "{}");
            if (p.output_asset_id) setOutputAssetId(p.output_asset_id);
          } catch {
            /* ignore */
          }
          void onChange();
        }
      });
    }, 1500);
    return () => clearInterval(t);
  }, [job, onChange]);

  const generate = async (edit?: { op: string; source_asset_id: string }) => {
    setBusy(true);
    setMsg(null);
    try {
      const nextHist = [prompt, ...history.filter((h) => h !== prompt)].slice(0, 20);
      setHistory(nextHist);
      localStorage.setItem("adept_imagegen_history", JSON.stringify(nextHist));
      const j = await api.imagegen(project.id, {
        prompt,
        negative,
        style,
        aspect,
        width: size.width,
        height: size.height,
        model,
        loras: loraStack,
        refs,
        edit: Boolean(edit),
        edit_op: edit?.op,
        source_asset_id: edit?.source_asset_id,
        denoise: edit ? 0.45 : 1,
      });
      setJob(j as Job);
    } catch (e: any) {
      setMsg(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const promote = async (target: string, extra: Record<string, unknown> = {}) => {
    if (!outputAssetId) {
      setMsg("Generate first.");
      return;
    }
    await api.promote(project.id, { asset_id: outputAssetId, target, ...extra });
    await onChange();
    setMsg(`Promoted → ${target}`);
  };

  const images = project.assets.filter((a) => a.kind === "image");

  return (
    <div className="page gen-workspace">
      <h1>ImageGen</h1>
      <p className="muted">Model-agnostic Comfy path — production stills for Profiles, Director, and storyboards.</p>
      {msg && <p className="pill warn">{msg}</p>}

      <div className="field">
        <label>Prompt</label>
        <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={4} />
      </div>
      <div className="field">
        <label>Negative</label>
        <textarea value={negative} onChange={(e) => setNegative(e.target.value)} rows={2} />
      </div>
      <div className="field">
        <label>History</label>
        <select value="" onChange={(e) => e.target.value && setPrompt(e.target.value)}>
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
          <label>Style</label>
          <select value={style} onChange={(e) => setStyle(e.target.value as any)}>
            {IMAGE_STYLE_PRESETS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Aspect</label>
          <select value={aspect} onChange={(e) => setAspect(e.target.value)}>
            {ASPECT_PRESETS.map((a) => (
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
          <label>Model</label>
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            {(models.length ? models : [{ id: "auto", label: "Auto" }, { id: "flux", label: "FLUX" }]).map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="card" style={{ marginTop: "0.75rem" }}>
        <strong>Engine Auto Select · inspector</strong>
        <ul>
          {reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </div>

      <section style={{ marginTop: "1rem" }}>
        <h3>Reference images</h3>
        <div className="row" style={{ flexWrap: "wrap", gap: "0.4rem" }}>
          {REF_ROLES.map((role) => (
            <label key={role} className="pill">
              {role}{" "}
              <select
                value={refs.find((r) => r.role === role)?.assetId || ""}
                onChange={(e) => {
                  const assetId = e.target.value;
                  setRefs((prev) => {
                    const rest = prev.filter((r) => r.role !== role);
                    return assetId ? [...rest, { assetId, role }] : rest;
                  });
                }}
              >
                <option value="">—</option>
                {images.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.tag || a.filename}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
      </section>

      <div className="row" style={{ marginTop: "1rem", gap: "0.5rem" }}>
        <button type="button" onClick={() => setLoraOpen((v) => !v)}>
          LoRAs {loraOpen ? "▾" : "▸"}
        </button>
        <button type="button" className="primary" disabled={busy || !prompt.trim()} onClick={() => generate()}>
          {busy ? "Queuing…" : "Generate"}
        </button>
        <button type="button" onClick={() => onGo("marketplace")}>
          Marketplace
        </button>
        <button type="button" onClick={() => onGo("library")}>
          Library
        </button>
      </div>

      {loraOpen && (
        <LoRAManager
          scope={`project:${project.id}`}
          baseModel={model === "auto" ? "flux" : model}
          stack={loraStack}
          onStackChange={setLoraStack}
        />
      )}

      {job && (
        <p className="scene-meta" style={{ marginTop: "0.75rem" }}>
          Job {job.status} · {Math.round((job.progress || 0) * 100)}% — {job.message}
          {job.output_path && (
            <img
              src={api.mediaUrl(job.output_path)}
              alt="output"
              style={{ display: "block", maxWidth: 360, marginTop: 8, borderRadius: 8 }}
            />
          )}
        </p>
      )}

      {outputAssetId && (
        <>
          <div className="promote-bar">
            <h3>Promote</h3>
            <div className="row" style={{ flexWrap: "wrap", gap: "0.4rem" }}>
              <button type="button" onClick={() => promote("profile", { profile_kind: "character" })}>
                Character Profile
              </button>
              <button type="button" onClick={() => promote("profile", { profile_kind: "prop" })}>
                Prop
              </button>
              <button type="button" onClick={() => promote("profile", { profile_kind: "scene" })}>
                Scene Profile
              </button>
              <button type="button" onClick={() => promote("tag", { tag: "storyboard" })}>
                Storyboard tag
              </button>
              <button
                type="button"
                onClick={() =>
                  promote("scene_start", { scene_id: project.scenes[0]?.id })
                }
              >
                Start
              </button>
              <button
                type="button"
                onClick={() => promote("scene_middle", { scene_id: project.scenes[0]?.id })}
              >
                Middle
              </button>
              <button type="button" onClick={() => promote("scene_end", { scene_id: project.scenes[0]?.id })}>
                End
              </button>
              <button type="button" onClick={() => promote("scene_new")}>
                Director scene
              </button>
              <button type="button" onClick={() => onGo("one")}>
                1 Frame
              </button>
              <button type="button" onClick={() => onGo("three")}>
                3 Frame
              </button>
              <button type="button" onClick={() => onGo("spatial")}>
                Spatial
              </button>
            </div>
          </div>

          <div className="promote-bar">
            <h3>Edit tools (enqueue img2img stubs)</h3>
            <div className="row" style={{ flexWrap: "wrap", gap: "0.4rem" }}>
              {EDIT_OPS.map((op) => (
                <button
                  key={op}
                  type="button"
                  disabled={busy}
                  onClick={() => generate({ op, source_asset_id: outputAssetId })}
                >
                  {op.replace(/_/g, " ")}
                </button>
              ))}
            </div>
          </div>
        </>
      )}

      <div style={{ marginTop: "1.25rem" }}>
        <JobPanel projectId={project.id} onDone={() => void onChange()} />
      </div>
    </div>
  );
}
