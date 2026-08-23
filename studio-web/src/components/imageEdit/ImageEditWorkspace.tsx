import { useCallback, useEffect, useMemo, useState } from "react";
import { shouldSuspendDependentPolling } from "../../runtime/studioApiConnection";
import {
  api,
  type ImageProductEditRecommendation,
  type ImageProductRecipe,
  type ImageProductVersion,
} from "../../api";
import type { Job, Project } from "../../types";
import { JobPanel } from "../JobPanel";
import { ImageMaskEditor } from "./ImageMaskEditor";

const EDIT_OPERATIONS = [
  { value: "image.inpaint", label: "Inpaint" },
  { value: "image.object_remove", label: "Remove object" },
  { value: "image.object_replace", label: "Replace object" },
  { value: "image.outpaint", label: "Outpaint" },
  { value: "image.background_remove", label: "Remove background" },
  { value: "image.background_replace", label: "Replace background" },
  { value: "image.face_restore", label: "Face restore" },
  { value: "image.reference_edit", label: "Reference edit" },
  { value: "image.style_transfer", label: "Style transfer" },
  { value: "image.relight", label: "Relight" },
  { value: "image.recolor", label: "Recolor" },
  { value: "image.upscale", label: "Upscale" },
  { value: "image.crop_extend", label: "Crop / extend" },
] as const;

const PRESERVE_KEYS = [
  "preserveComposition",
  "preserveSubject",
  "preserveBackground",
  "preserveLighting",
  "preservePalette",
] as const;

const DEFAULT_LAYERS = () => [
  { layerId: "layer-bg", name: "Background", visible: true, kind: "background" },
  { layerId: "layer-fg", name: "Foreground", visible: true, kind: "foreground" },
  { layerId: "layer-mask", name: "Masks", visible: true, kind: "mask", opacity: 0.5 },
  { layerId: "layer-ref", name: "References", visible: true, kind: "reference" },
];

export function ImageEditWorkspace({
  project,
  onChange,
}: {
  project: Project;
  onChange: () => Promise<void>;
}) {
  const images = useMemo(() => project.assets.filter((a) => a.kind === "image"), [project.assets]);

  const [sourceAssetId, setSourceAssetId] = useState("");
  const [recipes, setRecipes] = useState<ImageProductRecipe[]>([]);
  const [recipeId, setRecipeId] = useState("");
  const [operation, setOperation] = useState("image.inpaint");
  const [prompt, setPrompt] = useState("");
  const [negative, setNegative] = useState(project.negative_prompt || "");
  const [strength, setStrength] = useState(0.75);
  const [preserve, setPreserve] = useState<Record<string, boolean>>({
    preserveComposition: true,
    preserveSubject: true,
    preserveBackground: true,
    preserveLighting: true,
    preservePalette: true,
  });
  const [layers, setLayers] = useState(DEFAULT_LAYERS());
  const [maskBase64, setMaskBase64] = useState<string | null>(null);
  const [savedMaskId, setSavedMaskId] = useState<string | null>(null);
  const [hasMask, setHasMask] = useState(false);
  const [recommendation, setRecommendation] = useState<ImageProductEditRecommendation | null>(null);
  const [recBusy, setRecBusy] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [versions, setVersions] = useState<ImageProductVersion[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [reviewNote, setReviewNote] = useState("");
  const [batchTargets, setBatchTargets] = useState<string[]>([]);
  const [gateOk, setGateOk] = useState<boolean | null>(null);

  const sourceAsset = images.find((a) => a.id === sourceAssetId);
  const imageUrl = sourceAsset ? api.assetUrl(sourceAsset.id) : "";

  const refreshRecipes = useCallback(async () => {
    try {
      const res = await api.imageProduct.listRecipes(project.id);
      setRecipes(res.recipes || []);
    } catch {
      setRecipes([]);
    }
  }, [project.id]);

  const refreshVersions = useCallback(async () => {
    try {
      const res = await api.imageProduct.listVersions(project.id);
      setVersions(res.versions || []);
    } catch {
      setVersions([]);
    }
  }, [project.id]);

  useEffect(() => {
    void refreshRecipes();
    void refreshVersions();
    api.imageProduct.gateWave4().then((g) => setGateOk(Boolean(g?.ok ?? g?.passed))).catch(() => setGateOk(null));
  }, [project.id, refreshRecipes, refreshVersions]);

  useEffect(() => {
    if (!sourceAssetId && images.length) setSourceAssetId(images[0].id);
  }, [images, sourceAssetId]);

  const applyRecipe = (id: string) => {
    setRecipeId(id);
    const recipe = recipes.find((r) => r.recipeId === id);
    if (!recipe) return;
    if (recipe.operation) setOperation(recipe.operation);
    if (recipe.preserveToggles) setPreserve((p) => ({ ...p, ...recipe.preserveToggles }));
    if (recipe.promptTemplate) setPrompt(recipe.promptTemplate.replace("{detail}", prompt || ""));
  };

  useEffect(() => {
    if (!sourceAssetId && !operation) {
      setRecommendation(null);
      return;
    }
    const t = setTimeout(() => {
      setRecBusy(true);
      api.imageProduct
        .editRecommend({
          operation,
          prompt,
          sourceAssetIds: sourceAssetId ? [sourceAssetId] : [],
          masks: hasMask || savedMaskId,
          quality: "standard",
        })
        .then(setRecommendation)
        .catch(() => setRecommendation(null))
        .finally(() => setRecBusy(false));
    }, 400);
    return () => clearTimeout(t);
  }, [operation, prompt, sourceAssetId, hasMask, savedMaskId]);

  useEffect(() => {
    const activeJobs = jobs.filter((j) => !["done", "failed", "cancelled"].includes(j.status));
    if (!activeJobs.length) return;
    const tick = setInterval(() => {
      if (shouldSuspendDependentPolling()) return;
      Promise.all(activeJobs.map((j) => api.getJob(j.id)))
        .then((updated) => {
          setJobs((prev) => {
            const map = new Map(updated.map((j) => [j.id, j]));
            return prev.map((j) => map.get(j.id) || j);
          });
          if (updated.some((j) => j.status === "done")) {
            void onChange();
            void refreshVersions();
          }
        })
        .catch(() => undefined);
    }, 1500);
    return () => clearInterval(tick);
  }, [jobs, onChange, refreshVersions]);

  const saveMaskToApi = async (base64: string) => {
    if (!sourceAssetId) return null;
    try {
      const saved = await api.imageProduct.saveMask(project.id, {
        sourceAssetId,
        pngBase64: base64,
        role: "include",
        metadata: { feather: 0 },
      });
      setSavedMaskId(saved.maskId);
      return saved.maskId;
    } catch (e: any) {
      setMsg(e?.message || "Mask save failed");
      return null;
    }
  };

  const executeEdit = async () => {
    if (!sourceAssetId) {
      setMsg("Select a source image.");
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      let maskId = savedMaskId;
      if (maskBase64 && !maskId) {
        maskId = await saveMaskToApi(maskBase64);
      }
      const masks = maskId ? [{ maskId, role: "include" }] : [];
      const body: Record<string, unknown> = {
        projectId: project.id,
        sourceAssetId,
        operation,
        prompt,
        negativePrompt: negative,
        recipeId: recipeId || undefined,
        masks,
        layers,
        preferences: { strength, preserve },
        controls: { strength },
      };
      const result = await api.imageProduct.editEnqueue(body);
      if (result.jobId) {
        const job = await api.getJob(result.jobId);
        setJobs((prev) => [job, ...prev.filter((j) => j.id !== job.id)]);
      }
      if (result.recommendation) setRecommendation(result.recommendation);
      setMsg(`Queued edit · ${result.workflowKey || result.operation}`);
    } catch (e: any) {
      setMsg(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const executeBatch = async () => {
    if (!batchTargets.length) {
      setMsg("Select batch target assets.");
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      let maskId = savedMaskId;
      if (maskBase64 && !maskId) maskId = await saveMaskToApi(maskBase64);
      const body: Record<string, unknown> = {
        projectId: project.id,
        sourceAssetId,
        targetAssetIds: batchTargets,
        operation,
        prompt,
        negativePrompt: negative,
        recipeId: recipeId || undefined,
        masks: maskId ? [{ maskId, role: "include" }] : [],
        preferences: { strength, preserve },
      };
      const result = await api.imageProduct.editBatch(body);
      const ids = (result.jobs || []).map((j) => j.jobId).filter(Boolean) as string[];
      const fetched = await Promise.all(ids.map((id) => api.getJob(id)));
      setJobs((prev) => [...fetched, ...prev.filter((j) => !ids.includes(j.id))]);
      setMsg(`Batch queued · ${ids.length} job(s)`);
    } catch (e: any) {
      setMsg(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const approveVersion = async (versionId: string, state: string) => {
    try {
      if (reviewNote.trim()) {
        await api.imageProduct.patchVersion(project.id, versionId, {
          reviewNote: { author: "user", text: reviewNote.trim() },
        });
      }
      await api.imageProduct.patchVersion(project.id, versionId, { state });
      setReviewNote("");
      void refreshVersions();
      setMsg(`Version → ${state}`);
    } catch (e: any) {
      setMsg(e?.message || String(e));
    }
  };

  const markProductionMaster = async (versionId: string) => {
    try {
      await api.imageProduct.patchVersion(project.id, versionId, { markMaster: true });
      void refreshVersions();
      setMsg("Promoted to Production Master");
    } catch (e: any) {
      setMsg(e?.message || String(e));
    }
  };

  const pendingVersions = versions.filter((v) => v.state === "PendingReview");
  const displayEstimates = recommendation?.executionEstimates || recommendation?.estimates;

  return (
    <div className="page gen-workspace image-edit-workspace">
      <h1>Edit Studio</h1>
      <p className="muted">
        M42 Wave 4 — certified edit path with masks, recipes, version graph, and batch apply.
      </p>
      {gateOk === false && <p className="pill warn">Wave 4 gate not passed — some edit paths may be blocked.</p>}
      {msg && <p className="pill warn">{msg}</p>}

      <div className="gen-grid" style={{ marginBottom: "0.75rem" }}>
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
        <div className="field">
          <label>Recipe</label>
          <select value={recipeId} onChange={(e) => applyRecipe(e.target.value)}>
            <option value="">None</option>
            {recipes.map((r) => (
              <option key={r.recipeId} value={r.recipeId}>
                {r.name}
                {r.builtin ? " (built-in)" : ""}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Operation</label>
          <select value={operation} onChange={(e) => setOperation(e.target.value)}>
            {EDIT_OPERATIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Strength</label>
          <input
            type="range"
            min={0.1}
            max={1}
            step={0.05}
            value={strength}
            onChange={(e) => setStrength(Number(e.target.value))}
          />
          <span className="scene-meta">{Math.round(strength * 100)}%</span>
        </div>
      </div>

      <div className="gen-grid" style={{ marginBottom: "0.75rem" }}>
        <div className="field">
          <label>Prompt</label>
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} />
        </div>
        <div className="field">
          <label>Negative</label>
          <textarea value={negative} onChange={(e) => setNegative(e.target.value)} rows={3} />
        </div>
      </div>

      <section style={{ marginBottom: "1rem" }}>
        <h3>Preserve</h3>
        <div className="row" style={{ flexWrap: "wrap", gap: "0.4rem" }}>
          {PRESERVE_KEYS.map((key) => (
            <label key={key} className="pill">
              <input
                type="checkbox"
                checked={preserve[key] !== false}
                onChange={(e) => setPreserve((p) => ({ ...p, [key]: e.target.checked }))}
              />{" "}
              {key.replace("preserve", "")}
            </label>
          ))}
        </div>
      </section>

      {(recommendation || recBusy) && (
        <div className="card" style={{ marginBottom: "0.75rem" }}>
          <strong>Recommendation {recBusy ? "…" : ""}</strong>
          {recommendation && (
            <>
              <p style={{ margin: "0.5rem 0" }}>{recommendation.whyThisModel}</p>
              {recommendation.maskStrategy && recommendation.maskStrategy !== "none" && (
                <p className="scene-meta">Mask strategy: {recommendation.maskStrategy}</p>
              )}
              <div className="gen-grid">
                <div className="field">
                  <label>Execution family</label>
                  <div>{recommendation.executionFamily}</div>
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
            </>
          )}
        </div>
      )}

      <section style={{ marginBottom: "1rem" }}>
        <h3>Mask editor</h3>
        {imageUrl ? (
          <ImageMaskEditor
            imageUrl={imageUrl}
            onExport={(b64) => {
              setMaskBase64(b64);
              setHasMask(true);
            }}
            onChange={setHasMask}
          />
        ) : (
          <p className="muted">Select a source image to paint a mask.</p>
        )}
        {savedMaskId && <p className="scene-meta">Saved mask: {savedMaskId.slice(0, 12)}…</p>}
      </section>

      <section style={{ marginBottom: "1rem" }}>
        <h3>Layers</h3>
        <div className="row" style={{ flexWrap: "wrap", gap: "0.35rem" }}>
          {layers.map((layer) => (
            <label key={layer.layerId} className="pill">
              <input
                type="checkbox"
                checked={layer.visible !== false}
                onChange={(e) =>
                  setLayers((prev) =>
                    prev.map((l) => (l.layerId === layer.layerId ? { ...l, visible: e.target.checked } : l))
                  )
                }
              />{" "}
              {layer.name}
            </label>
          ))}
        </div>
      </section>

      <section style={{ marginBottom: "1rem" }}>
        <h3>History strip</h3>
        <div className="row" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
          {(["Original", "Mask", "Edited", "Approved"] as const).map((label) => (
            <div
              key={label}
              className="card"
              style={{
                width: 88,
                height: 72,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                opacity: label === "Original" && sourceAsset ? 1 : 0.5,
              }}
            >
              {label === "Original" && sourceAsset ? (
                <img
                  src={api.assetUrl(sourceAsset.id)}
                  alt="original"
                  style={{ maxWidth: "100%", maxHeight: "100%", borderRadius: 4 }}
                />
              ) : (
                <span className="scene-meta">{label}</span>
              )}
            </div>
          ))}
        </div>
      </section>

      <section style={{ marginBottom: "1rem" }}>
        <h3>Versions</h3>
        {versions.length === 0 && <p className="muted">No edit versions yet — run an edit to create one.</p>}
        <div className="gen-grid">
          {versions.slice(0, 8).map((v) => (
            <div
              key={v.versionId}
              className="card"
              style={{
                borderColor: selectedVersionId === v.versionId ? "var(--accent)" : undefined,
                cursor: "pointer",
              }}
              onClick={() => setSelectedVersionId(v.versionId)}
            >
              <strong>{v.name}</strong>
              <div className="scene-meta">{v.state}</div>
              {v.reviewNotes?.length ? (
                <div className="scene-meta">{v.reviewNotes[v.reviewNotes.length - 1]?.text?.slice(0, 60)}</div>
              ) : null}
            </div>
          ))}
        </div>
        {(selectedVersionId || pendingVersions.length > 0) && (
          <div style={{ marginTop: "0.75rem" }}>
            <div className="field">
              <label>Review note</label>
              <input value={reviewNote} onChange={(e) => setReviewNote(e.target.value)} placeholder="Optional note…" />
            </div>
            <div className="row" style={{ gap: "0.4rem", flexWrap: "wrap" }}>
              <button
                type="button"
                className="primary"
                onClick={() => selectedVersionId && approveVersion(selectedVersionId, "Approved")}
              >
                Approve
              </button>
              <button
                type="button"
                onClick={() => selectedVersionId && approveVersion(selectedVersionId, "PendingReview")}
              >
                Pending review
              </button>
              <button
                type="button"
                onClick={() => selectedVersionId && approveVersion(selectedVersionId, "Rejected")}
              >
                Reject
              </button>
              <button type="button" onClick={() => selectedVersionId && markProductionMaster(selectedVersionId)}>
                Production master
              </button>
            </div>
          </div>
        )}
      </section>

      <section style={{ marginBottom: "1rem" }}>
        <h3>Batch apply</h3>
        <p className="scene-meta">Apply the current edit recipe to multiple target assets.</p>
        <div className="row" style={{ flexWrap: "wrap", gap: "0.35rem", marginBottom: "0.5rem" }}>
          {images
            .filter((a) => a.id !== sourceAssetId)
            .map((a) => (
              <label key={a.id} className="pill">
                <input
                  type="checkbox"
                  checked={batchTargets.includes(a.id)}
                  onChange={(e) =>
                    setBatchTargets((prev) =>
                      e.target.checked ? [...prev, a.id] : prev.filter((id) => id !== a.id)
                    )
                  }
                />{" "}
                {a.tag || a.filename}
              </label>
            ))}
        </div>
        <button type="button" disabled={busy || !batchTargets.length} onClick={() => void executeBatch()}>
          Batch edit ({batchTargets.length})
        </button>
      </section>

      <div className="row" style={{ gap: "0.5rem", marginBottom: "1rem" }}>
        <button type="button" className="primary" disabled={busy || !sourceAssetId} onClick={() => void executeEdit()}>
          {busy ? "Queuing…" : "Run edit"}
        </button>
      </div>

      {jobs.map((job) => (
        <div key={job.id} className="card" style={{ marginBottom: "0.5rem" }}>
          <div className="scene-head">
            <strong>{job.kind}</strong>
            <span className="pill">{job.status}</span>
          </div>
          <div className="scene-meta">
            {Math.round((job.progress || 0) * 100)}% — {job.message}
            {job.stage ? ` · ${job.stage}` : ""}
          </div>
          <div className="bar">
            <i style={{ width: `${Math.round((job.progress || 0) * 100)}%` }} />
          </div>
        </div>
      ))}

      <JobPanel projectId={project.id} onDone={() => void onChange()} />
    </div>
  );
}
