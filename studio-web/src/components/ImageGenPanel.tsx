/** Dead route — not wired into product chrome (Stability Cull). Keep for historical tests only. */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  type ImageProductFamily,
  type ImageProductPreset,
  type ImageProductRecommendation,
} from "../api";
import type { Job, Project } from "../types";
import { ASPECT_PRESETS, type EditorTab } from "../workspacePrefs";
import { LoRAManager } from "./LoRAManager";
import { JobPanel } from "./JobPanel";
import { StatusBadge } from "./ui";
import { ImageEditWorkspace } from "./imageEdit/ImageEditWorkspace";
import { GenerateContinuitySection } from "./continuity/GenerateContinuitySection";
import { PromptIntelligencePanel } from "./CoDirector/PromptIntelligencePanel";
import type { StatusKind } from "../status";

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

const PURPOSE_OPTIONS = [
  { value: "", label: "General" },
  { value: "concept_art", label: "Concept art" },
  { value: "storyboard", label: "Storyboard" },
  { value: "marketing", label: "Marketing" },
  { value: "production_still", label: "Production still" },
  { value: "poster", label: "Poster" },
  { value: "character_sheet", label: "Character sheet" },
] as const;

type GenMode = "txt2img" | "img2img" | "reference";
type StudioMode = "generate" | "edit";

function projectDefaults(project: Project): Record<string, any> {
  try {
    return project.defaults_json ? JSON.parse(project.defaults_json) : {};
  } catch {
    return {};
  }
}

function familyStatusKind(status: string): StatusKind {
  if (status === "Certified") return "Ready";
  if (status === "Draft") return "Partial";
  if (status === "Blocked") return "Blocked";
  if (status === "Deferred") return "Deferred";
  return "Unknown";
}

function operationForMode(mode: GenMode): string {
  if (mode === "img2img") return "image.edit";
  if (mode === "reference") return "image.reference";
  return "image.generate";
}

function applyPromptTemplate(template: string, subject: string): string {
  const sub = subject.trim() || "subject";
  return template.includes("{subject}") ? template.replace(/\{subject\}/g, sub) : `${template} ${sub}`.trim();
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
  const defaultFamily = String(d.imagegen_model || "auto");
  const initialFamilyPref = ["auto", "qwen2512", "zimage", "flux", "qwen", "imagen"].includes(defaultFamily)
    ? defaultFamily
    : "auto";

  const [prompt, setPrompt] = useState("");
  const [negative, setNegative] = useState(project.negative_prompt);
  const [purpose, setPurpose] = useState("");
  const [mode, setMode] = useState<GenMode>("txt2img");
  const [sourceAssetId, setSourceAssetId] = useState("");
  const [aspect, setAspect] = useState(String(d.aspect || "16:9"));
  const [resolution, setResolution] = useState("1080p");
  const [quality, setQuality] = useState<"standard" | "high">("standard");
  const [familyPref, setFamilyPref] = useState(initialFamilyPref);
  const [families, setFamilies] = useState<ImageProductFamily[]>([]);
  const [presets, setPresets] = useState<ImageProductPreset[]>([]);
  const [presetId, setPresetId] = useState("");
  const [seed, setSeed] = useState(project.seed ?? -1);
  const [batchCount, setBatchCount] = useState(1);
  const [refs, setRefs] = useState<{ assetId: string; role: string }[]>([]);
  const [loraOpen, setLoraOpen] = useState(false);
  const [loraStack, setLoraStack] = useState<any[]>([]);
  const [recommendation, setRecommendation] = useState<ImageProductRecommendation | null>(null);
  const [recBusy, setRecBusy] = useState(false);
  const [overrideFamily, setOverrideFamily] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [outputAssetId, setOutputAssetId] = useState<string | null>(null);
  const [promptHistory, setPromptHistory] = useState<string[]>([]);
  const [studioMode, setStudioMode] = useState<StudioMode>("generate");

  const effectiveFamily = overrideFamily || (familyPref === "auto" ? null : familyPref);
  const selectedFamilyMeta = useMemo(
    () => families.find((f) => f.family === (effectiveFamily || recommendation?.executionFamily)),
    [families, effectiveFamily, recommendation?.executionFamily]
  );

  const refreshPresets = useCallback(async () => {
    try {
      const res = await api.imageProduct.listPresets(project.id);
      setPresets(res.presets || []);
    } catch {
      setPresets([]);
    }
  }, [project.id]);

  const refreshPromptHistory = useCallback(async () => {
    try {
      const res = await api.imageProduct.promptHistory(project.id);
      setPromptHistory(res.prompts || []);
    } catch {
      try {
        const hist = await api.imageProduct.history(project.id, 20);
        setPromptHistory(hist.prompts || []);
      } catch {
        setPromptHistory([]);
      }
    }
  }, [project.id]);

  useEffect(() => {
    api.imageProduct.families().then((r) => setFamilies(r.families || [])).catch(() => setFamilies([]));
    void refreshPresets();
    void refreshPromptHistory();
    api.loraStack(`project:${project.id}`).then((r) => setLoraStack(r.stack || [])).catch(() => undefined);
  }, [project.id, refreshPresets, refreshPromptHistory]);

  useEffect(() => {
    if (!prompt.trim() && !purpose) {
      setRecommendation(null);
      return;
    }
    const t = setTimeout(() => {
      setRecBusy(true);
      api.imageProduct
        .recommend({
          prompt,
          purpose,
          operation: operationForMode(mode),
          modelFamilyPreference: effectiveFamily || undefined,
          quality,
        })
        .then(setRecommendation)
        .catch(() => setRecommendation(null))
        .finally(() => setRecBusy(false));
    }, 400);
    return () => clearTimeout(t);
  }, [prompt, purpose, mode, effectiveFamily, quality]);

  useEffect(() => {
    const activeJobs = jobs.filter((j) => !["done", "failed", "cancelled"].includes(j.status));
    if (!activeJobs.length) return;
    const tick = setInterval(() => {
      Promise.all(activeJobs.map((j) => api.getJob(j.id)))
        .then((updated) => {
          setJobs((prev) => {
            const map = new Map(updated.map((j) => [j.id, j]));
            return prev.map((j) => map.get(j.id) || j);
          });
          const done = updated.filter((j) => j.status === "done");
          if (done.length) {
            for (const j of done) {
              try {
                const p = JSON.parse(j.params_json || "{}");
                if (p.output_asset_id) setOutputAssetId(p.output_asset_id);
              } catch {
                /* ignore */
              }
            }
            void onChange();
            void refreshPromptHistory();
          }
        })
        .catch(() => undefined);
    }, 1500);
    return () => clearInterval(tick);
  }, [jobs, onChange, refreshPromptHistory]);

  const applyPreset = (id: string) => {
    setPresetId(id);
    const preset = presets.find((p) => p.presetId === id);
    if (!preset) return;
    if (preset.preferredModelFamily) {
      setFamilyPref(preset.preferredModelFamily);
      setOverrideFamily(null);
    }
    if (preset.aspectRatio) setAspect(preset.aspectRatio);
    if (preset.qualityPreset) setQuality(preset.qualityPreset === "high" ? "high" : "standard");
    if (preset.resolution) setResolution(preset.resolution);
    if (preset.promptTemplate) {
      setPrompt(applyPromptTemplate(preset.promptTemplate, prompt));
    }
  };

  const generate = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const body: Record<string, unknown> = {
        purpose,
        prompt,
        negativePrompt: negative,
        operation: operationForMode(mode),
        aspectRatio: aspect,
        resolution,
        quality,
        seed: seed >= 0 ? seed : undefined,
        batchCount,
        presetId: presetId || undefined,
        refs,
        loras: loraStack,
      };
      if (effectiveFamily) body.modelFamilyPreference = effectiveFamily;
      if (mode !== "txt2img" && sourceAssetId) body.sourceAssetId = sourceAssetId;

      const result = await api.imageProduct.generate(project.id, body);
      const queuedIds = (result.jobs || []).map((j) => j.jobId).filter(Boolean) as string[];
      const primaryId = result.jobId || queuedIds[0];
      const fetched = await Promise.all(queuedIds.map((id) => api.getJob(id)));
      setJobs(fetched.length ? fetched : primaryId ? [await api.getJob(primaryId)] : []);
      if (result.recommendation) setRecommendation(result.recommendation);
      void refreshPromptHistory();
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
  const displayEstimates = recommendation?.executionEstimates || recommendation?.estimates;
  const displayFamily = overrideFamily || recommendation?.executionFamily || effectiveFamily || "zimage";

  if (studioMode === "edit") {
    return (
      <div>
        <div className="row" style={{ gap: "0.5rem", marginBottom: "0.75rem" }}>
          <button type="button" onClick={() => setStudioMode("generate")}>
            Generate
          </button>
          <button type="button" className="primary" onClick={() => setStudioMode("edit")}>
            Edit
          </button>
        </div>
        <ImageEditWorkspace project={project} onChange={onChange} />
      </div>
    );
  }

  return (
    <div className="page gen-workspace">
      <div className="row" style={{ gap: "0.5rem", marginBottom: "0.75rem" }}>
        <button type="button" className="primary" onClick={() => setStudioMode("generate")}>
          Generate
        </button>
        <button type="button" onClick={() => setStudioMode("edit")}>
          Edit
        </button>
      </div>
      <h1>Generate Studio</h1>
      <p className="muted">
        Image Product path — family-aware generation with certified workflow resolver (no manual workflow keys).
      </p>
      {msg && <p className="pill warn">{msg}</p>}
      <GenerateContinuitySection projectId={project.id} />

      <div className="gen-grid" style={{ marginBottom: "0.75rem" }}>
        <div className="field">
          <label>Session preset</label>
          <select value={presetId} onChange={(e) => applyPreset(e.target.value)}>
            <option value="">None</option>
            {presets.map((p) => (
              <option key={p.presetId} value={p.presetId}>
                {p.name}
                {p.builtin ? " (built-in)" : ""}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Purpose</label>
          <select value={purpose} onChange={(e) => setPurpose(e.target.value)}>
            {PURPOSE_OPTIONS.map((p) => (
              <option key={p.value || "general"} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Mode</label>
          <select value={mode} onChange={(e) => setMode(e.target.value as GenMode)}>
            <option value="txt2img">Text → image</option>
            <option value="img2img">Image → image</option>
            <option value="reference">Reference-guided</option>
          </select>
        </div>
        <div className="field">
          <label>Batch</label>
          <select value={batchCount} onChange={(e) => setBatchCount(Number(e.target.value))}>
            {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
              <option key={n} value={n}>
                {n} job{n > 1 ? "s" : ""}
              </option>
            ))}
          </select>
        </div>
      </div>

      <section style={{ marginBottom: "1rem" }}>
        <h3>Model family</h3>
        <div className="row" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
          <button
            type="button"
            className={familyPref === "auto" && !overrideFamily ? "primary" : ""}
            onClick={() => {
              setFamilyPref("auto");
              setOverrideFamily(null);
            }}
          >
            Auto
          </button>
          {families.map((f) => (
            <button
              key={f.family}
              type="button"
              className={
                (overrideFamily || familyPref) === f.family ? "primary" : ""
              }
              disabled={!f.executable && f.status !== "Draft"}
              onClick={() => {
                setFamilyPref(f.family);
                setOverrideFamily(f.family);
              }}
              title={f.executable ? "Certified" : f.status}
            >
              {f.label}{" "}
              <StatusBadge kind={familyStatusKind(f.status)} label={f.status} compact />
            </button>
          ))}
        </div>
        {selectedFamilyMeta && (
          <p className="scene-meta" style={{ marginTop: 6 }}>
            {selectedFamilyMeta.estimates.generationTimeSec}s est.
            {selectedFamilyMeta.estimates.vramGb != null
              ? ` · ~${selectedFamilyMeta.estimates.vramGb} GB VRAM`
              : ""}
            {selectedFamilyMeta.estimates.costLabel ? ` · ${selectedFamilyMeta.estimates.costLabel}` : ""}
          </p>
        )}
      </section>

      <div className="field">
        <label>Prompt</label>
        <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={4} />
      </div>
      <PromptIntelligencePanel
        creatorPrompt={prompt}
        domain="image"
        providerId="comfyui"
        modelId={effectiveFamily || "flux"}
        projectId={project.id}
        negativePrompt={negative}
        compact
        onApply={({ finalProviderPrompt }) => setPrompt(finalProviderPrompt)}
      />
      <div className="field">
        <label>Negative</label>
        <textarea value={negative} onChange={(e) => setNegative(e.target.value)} rows={2} />
      </div>
      <div className="field">
        <label>Prompt history</label>
        <select value="" onChange={(e) => e.target.value && setPrompt(e.target.value)}>
          <option value="">Load previous…</option>
          {promptHistory.map((h) => (
            <option key={h} value={h}>
              {h.slice(0, 80)}
            </option>
          ))}
        </select>
      </div>

      <div className="gen-grid">
        <div className="field">
          <label>Aspect</label>
          <select value={aspect} onChange={(e) => setAspect(e.target.value)}>
            {ASPECT_PRESETS.filter((a) => a !== "custom").map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Resolution</label>
          <select value={resolution} onChange={(e) => setResolution(e.target.value)}>
            {["720p", "1080p", "2K", "4K"].map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Quality</label>
          <select value={quality} onChange={(e) => setQuality(e.target.value as "standard" | "high")}>
            <option value="standard">Standard</option>
            <option value="high">High</option>
          </select>
        </div>
        <div className="field">
          <label>Seed (-1 = random)</label>
          <input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} />
        </div>
      </div>

      {(mode === "img2img" || mode === "reference") && (
        <div className="field">
          <label>Source image</label>
          <select value={sourceAssetId} onChange={(e) => setSourceAssetId(e.target.value)}>
            <option value="">Select…</option>
            {images.map((a) => (
              <option key={a.id} value={a.id}>
                {a.tag || a.filename}
              </option>
            ))}
          </select>
        </div>
      )}

      {(recommendation || recBusy) && (
        <div className="card" style={{ marginTop: "0.75rem" }}>
          <strong>Recommendation {recBusy ? "…" : ""}</strong>
          {recommendation && (
            <>
              <p style={{ margin: "0.5rem 0" }}>{recommendation.whyThisModel}</p>
              <div className="gen-grid">
                <div className="field">
                  <label>Execution family (override)</label>
                  <select
                    value={displayFamily}
                    onChange={(e) => setOverrideFamily(e.target.value)}
                  >
                    {(
                      [
                        ["qwen2512", "Qwen-Image-2512 (Recommended)"],
                        ["flux", "FLUX (Alternative)"],
                        ["zimage", "Z-Image (Fallback)"],
                        ["qwen", "Qwen (Legacy)"],
                        ["imagen", "Imagen (Cloud)"],
                      ] as const
                    ).map(([fam, label]) => (
                      <option key={fam} value={fam}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label>Est. time</label>
                  <div>{displayEstimates?.generationTimeSec ?? "—"}s</div>
                </div>
                <div className="field">
                  <label>VRAM / cost</label>
                  <div>
                    {displayEstimates?.vramGb != null ? `${displayEstimates.vramGb} GB` : "Cloud"}
                    {displayEstimates?.costLabel ? ` · ${displayEstimates.costLabel}` : ""}
                  </div>
                </div>
              </div>
              {recommendation.fallbackApplied && (
                <p className="scene-meta">Fallback applied — preferred family not executable; using certified path.</p>
              )}
            </>
          )}
        </div>
      )}

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
        <button
          type="button"
          className="primary"
          disabled={
            busy ||
            !prompt.trim() ||
            ((mode === "img2img" || mode === "reference") && !sourceAssetId)
          }
          onClick={() => generate()}
        >
          {busy ? "Queuing…" : batchCount > 1 ? `Generate ${batchCount}` : "Generate"}
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
          baseModel={displayFamily}
          stack={loraStack}
          onStackChange={setLoraStack}
        />
      )}

      {jobs.map((job) => (
        <p className="scene-meta" key={job.id} style={{ marginTop: "0.75rem" }}>
          Job {job.id.slice(0, 8)} · {job.status} · {Math.round((job.progress || 0) * 100)}% — {job.message}
          {job.stage ? ` · ${job.stage}` : ""}
          {job.output_path && (
            <img
              src={api.mediaUrl(job.output_path)}
              alt="output"
              style={{ display: "block", maxWidth: 360, marginTop: 8, borderRadius: 8 }}
            />
          )}
        </p>
      ))}

      {outputAssetId && (
        <div className="promote-bar">
          <h3>Promote</h3>
          <div className="row" style={{ flexWrap: "wrap", gap: "0.4rem" }}>
            <button type="button" onClick={() => promote("profile", { profile_kind: "character" })}>
              Character Profile
            </button>
            <button
              type="button"
              disabled
              title="Use Prop Creator to save a project prop"
              aria-disabled="true"
              data-testid="promote-prop-disabled"
            >
              Prop
            </button>
            <button type="button" onClick={() => promote("profile", { profile_kind: "scene" })}>
              Scene Profile
            </button>
            <button type="button" onClick={() => promote("tag", { tag: "storyboard" })}>
              Storyboard tag
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
          </div>
        </div>
      )}

      <div style={{ marginTop: "1.25rem" }}>
        <JobPanel projectId={project.id} onDone={() => void onChange()} />
      </div>
    </div>
  );
}
