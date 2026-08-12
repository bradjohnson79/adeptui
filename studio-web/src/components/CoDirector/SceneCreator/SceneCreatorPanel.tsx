/**
 * SceneCreatorPanel — the Scene Creator Co-Director right-pane tab.
 *
 * Consumes the Spatial Map (via ERS packages) and produces scene-shot images
 * ready for Timeline handoff.
 *
 * Flow:
 *  1. Resolve the most recent Environment Reference Sheet (ERS) for the
 *     project — empty state if none exists (amendment: ERS is downstream of
 *     Spatial Map).
 *  2. Resolve placed characters and props from the project's most recent
 *     Spatial Map document to drive @/# tag chips.
 *  3. Let the creator write shot requests (textarea), get one suggestion at
 *     a time, pick an output count, and Generate.
 *  4. The Agent Operation Overlay (handled by AgentWorkSurface) shows live
 *     progress during generation; this panel surfaces child job status on
 *     each result card.
 *  5. Persistence (Law #10): the most recent batch is reloaded on mount.
 *
 * Amendment #3 (spatial authority): Scene Creator images never mutate spatial
 * state — this panel is read-only against the spatial map.
 * Amendment #42 (output count): generate exactly len(shots); output_count is
 * capped by the number of parsed shots.
 * Amendment #44 (one suggestion at a time): handled in ShotRequestInput.
 * Amendment #48 (targeted regen): only the targeted shot's image changes.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../../../api";
import type {
  EnvironmentReferenceSheet,
  EnvironmentReferenceSheetSummary,
} from "../../../contracts/environmentReferenceSheet";
import type {
  SpatialCharacterPlacement,
  SpatialMapDocument,
  SpatialPropPlacement,
} from "../../../contracts/spatialMapM411";
import { useCoDirectorSession } from "../CoDirectorSession";
import { CoDirectorEmptyState } from "../cards";
import { ErsSelector } from "./ErsSelector";
import { sceneCreatorApi } from "./sceneCreatorApi";
import { SceneResultGrid } from "./SceneResultGrid";
import { ShotRequestInput } from "./ShotRequestInput";
import type {
  ChildJobSummary,
  ResolvedCharacter,
  ResolvedProp,
  SceneGenerationBatch,
  ShotRequest,
} from "./types";

export type SceneCreatorPanelProps = {
  projectId: string;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
};

/** Descriptive position label derived from a spatial placement's coordinates. */
function positionSummary(p: { x: number; y: number; z: number }): string {
  let lateral = "center";
  if (p.x <= -1.5) lateral = "left";
  else if (p.x >= 1.5) lateral = "right";
  let depth = "midground";
  if (p.z <= -1.5) depth = "foreground";
  else if (p.z >= 1.5) depth = "background";
  return `${depth} ${lateral}`.trim();
}

function normalizeTag(label: string): string {
  return label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "") || "prop";
}

const OUTPUT_COUNT_OPTIONS = [1, 2, 3, 4, 5, 6, 7, 8] as const;

export function SceneCreatorPanel({ projectId, onGoTab }: SceneCreatorPanelProps) {
  const { activeExecution } = useCoDirectorSession();

  const [sheets, setSheets] = useState<EnvironmentReferenceSheetSummary[]>([]);
  const [selectedSheetId, setSelectedSheetId] = useState<string>("");
  const [selectedSheet, setSelectedSheet] = useState<EnvironmentReferenceSheet | null>(null);
  const [spatialMaps, setSpatialMaps] = useState<SpatialMapDocument[]>([]);
  const [shotText, setShotText] = useState("");
  const [outputCount, setOutputCount] = useState<number>(4);
  const [visualStyle, setVisualStyle] = useState<string>("");

  const [batch, setBatch] = useState<SceneGenerationBatch | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [sendingShotIndex, setSendingShotIndex] = useState<number | null>(null);
  const [sendingBatch, setSendingBatch] = useState(false);
  const [loadingInitial, setLoadingInitial] = useState(true);

  // ------------------------------------------------------------------
  // Load ERS sheets + spatial map documents
  // ------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    setLoadingInitial(true);
    setError(null);
    void (async () => {
      try {
        const [sheetRes, mapRes] = await Promise.all([
          api.environmentReferenceSheet.listSheets(projectId),
          api.spatialMap.listMaps(projectId).catch(() => ({ documents: [] as SpatialMapDocument[] })),
        ]);
        if (cancelled) return;
        const nextSheets = sheetRes.sheets || [];
        setSheets(nextSheets);
        const maps = (mapRes.documents || []).sort((a, b) =>
          (b.updatedAt || "").localeCompare(a.updatedAt || ""),
        );
        setSpatialMaps(maps);
        if (nextSheets.length) {
          setSelectedSheetId((current) => {
            if (current && nextSheets.some((s) => s.sheetId === current)) return current;
            return nextSheets[0].sheetId;
          });
        } else {
          setSelectedSheetId("");
          setSelectedSheet(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!cancelled) setLoadingInitial(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  // Load the full selected sheet (for ERS name/status details).
  useEffect(() => {
    if (!selectedSheetId) {
      setSelectedSheet(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const res = await api.environmentReferenceSheet.getSheet(projectId, selectedSheetId);
        if (!cancelled) setSelectedSheet(res.sheet || null);
      } catch (err) {
        if (!cancelled) {
          // Non-fatal — the selector still works with the summary.
          setSelectedSheet(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, selectedSheetId]);

  // ------------------------------------------------------------------
  // Load the most recent batch on mount (persistence — Law #10)
  // ------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await sceneCreatorApi.listBatches(projectId);
        if (cancelled) return;
        const sorted = (res.batches || [])
          .slice()
          .sort((a: SceneGenerationBatch, b: SceneGenerationBatch) =>
            (b.updated_at || b.created_at || "").localeCompare(a.updated_at || a.created_at || ""),
          );
        if (sorted.length) {
          setBatch(sorted[0]);
          // Restore the shot text from the most recent batch for continuity.
          if (!shotText && sorted[0].shot_requests.length) {
            setShotText(sorted[0].shot_requests.map((s: ShotRequest) => s.raw_text).join(", "));
          }
          if (sorted[0].output_count) {
            setOutputCount(sorted[0].output_count);
          }
        }
      } catch {
        // No batch yet — that's fine.
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  // ------------------------------------------------------------------
  // Derive placed characters and props from the most recent spatial map.
  // Amendment #3: read-only — never writes back.
  // ------------------------------------------------------------------
  const { characters, props } = useMemo(() => {
    const map = spatialMaps[0];
    if (!map) return { characters: [] as ResolvedCharacter[], props: [] as ResolvedProp[] };
    const chars: ResolvedCharacter[] = (map.characters as SpatialCharacterPlacement[]).map((c) => ({
      character_id: c.characterId,
      name: c.label || c.characterId,
      position_label: positionSummary(c),
    }));
    const prps: ResolvedProp[] = (map.props as SpatialPropPlacement[]).map((p) => ({
      tag: normalizeTag(p.label),
      display_label: p.label,
      position_label: positionSummary(p),
    }));
    return { characters: chars, props: prps };
  }, [spatialMaps]);

  // ------------------------------------------------------------------
  // Live child jobs from the Agent Operation Overlay (scene_generation).
  // ------------------------------------------------------------------
  const childJobs: ChildJobSummary[] = useMemo(() => {
    if (!activeExecution) return [];
    if (activeExecution.surface_type !== "scene_generation") return [];
    return (activeExecution.child_jobs || []).map((c) => ({
      job_id: c.job_id,
      label: c.label,
      status: c.status,
      asset_id: c.asset_id,
      error: c.error,
      progress: c.progress,
      stage: c.stage,
      child_index: c.child_index,
    }));
  }, [activeExecution]);

  // ------------------------------------------------------------------
  // When an execution completes, reload the batch so result_asset_ids
  // reflect the real asset IDs (Law #10 — persistence after reload).
  // ------------------------------------------------------------------
  useEffect(() => {
    if (!activeExecution || activeExecution.surface_type !== "scene_generation") return;
    if (activeExecution.status !== "completed") return;
    if (!batch?.id) return;
    void (async () => {
      try {
        const res = await sceneCreatorApi.getBatch(projectId, batch.id);
        setBatch(res.batch);
      } catch {
        // Best-effort refresh.
      }
    })();
  }, [activeExecution?.status, activeExecution?.surface_type, activeExecution?.execution_id, projectId, batch?.id]);

  // ------------------------------------------------------------------
  // Generate
  // ------------------------------------------------------------------
  const handleGenerate = useCallback(async () => {
    if (!selectedSheetId) {
      setError("Select an Environment Reference Sheet first.");
      return;
    }
    if (!shotText.trim()) {
      setError("Write at least one shot request.");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await sceneCreatorApi.createBatch(projectId, {
        ers_package_id: selectedSheetId,
        shot_requests_raw: shotText,
        output_count: outputCount,
        visual_style: visualStyle || undefined,
        character_names: characters.map((c) => c.name),
      });
      setBatch(res.batch);
      setNotice(res.job_ids?.length ? `Generation started — ${res.job_ids.length} shot job${res.job_ids.length === 1 ? "" : "s"} queued.` : "Generation started.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [characters, outputCount, projectId, selectedSheetId, shotText, visualStyle]);

  // ------------------------------------------------------------------
  // Targeted regeneration (amendment #48)
  // ------------------------------------------------------------------
  const handleRegenerateShot = useCallback(
    async (shotIndex: number) => {
      if (!batch) return;
      setBusy(true);
      setError(null);
      setNotice(null);
      try {
        const shot = batch.shot_requests[shotIndex];
        const res = await sceneCreatorApi.regenerateShot(projectId, batch.id, {
          shot_index: shotIndex,
          new_prompt: shot?.raw_text || "",
          visual_style: visualStyle || undefined,
        });
        setBatch(res.batch);
        setNotice(`Shot ${shotIndex + 1} regenerated. Other shots remain intact.`);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
      }
    },
    [batch, projectId, visualStyle],
  );

  const handleEditPrompt = useCallback(
    async (shotIndex: number, newPrompt: string) => {
      if (!batch) return;
      setBusy(true);
      setError(null);
      setNotice(null);
      try {
        const res = await sceneCreatorApi.regenerateShot(projectId, batch.id, {
          shot_index: shotIndex,
          new_prompt: newPrompt,
          visual_style: visualStyle || undefined,
        });
        setBatch(res.batch);
        setNotice(`Shot ${shotIndex + 1} prompt updated and regenerated.`);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
      }
    },
    [batch, projectId, visualStyle],
  );

  // ------------------------------------------------------------------
  // Send to Timeline (per-shot and batch)
  // ------------------------------------------------------------------
  const sendShotToTimeline = useCallback(
    async (shotIndex: number) => {
      if (!batch) return;
      setSendingShotIndex(shotIndex);
      setError(null);
      setNotice(null);
      try {
        const res = await sceneCreatorApi.sendToTimeline(projectId, batch.id, {
          scene_id: selectedSheet?.sceneId || "",
          label: `Shot ${shotIndex + 1} — ${batch.shot_requests[shotIndex]?.framing || "scene"}`,
        });
        setNotice(`Shot ${shotIndex + 1} sent to Timeline (${res.clips_sent} clip${res.clips_sent === 1 ? "" : "s"}).`);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setSendingShotIndex(null);
      }
    },
    [batch, projectId, selectedSheet],
  );

  const sendBatchToTimeline = useCallback(async () => {
    if (!batch) return;
    setSendingBatch(true);
    setError(null);
    setNotice(null);
    try {
      const res = await sceneCreatorApi.sendToTimeline(projectId, batch.id, {
        scene_id: selectedSheet?.sceneId || "",
        label: `Scene Creator batch ${batch.id.slice(0, 8)}`,
      });
      setNotice(`Batch sent to Timeline (${res.clips_sent} clip${res.clips_sent === 1 ? "" : "s"}).`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSendingBatch(false);
    }
  }, [batch, projectId, selectedSheet]);

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  if (loadingInitial) {
    return (
      <p className="muted" data-testid="scene-creator-loading">
        Loading Scene Creator…
      </p>
    );
  }

  if (!sheets.length) {
    return (
      <CoDirectorEmptyState
        testId="scene-creator-empty-no-ers"
        title="Scene Creator"
        description="Create an Environment Reference Sheet in Spatial Map first. Scene Creator consumes the ERS package to generate scene-shot images."
        action={
          <button
            type="button"
            className="primary"
            onClick={() => onGoTab?.("spatial_map")}
            data-testid="scene-creator-open-spatial-map"
          >
            Open Spatial Map
          </button>
        }
      />
    );
  }

  return (
    <section data-testid="scene-creator-panel" className="codirector-content-card" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      <header>
        <h3 style={{ margin: 0 }}>Scene Creator</h3>
        <p className="muted" style={{ margin: "0.2rem 0 0", fontSize: "0.85rem" }}>
          Turn your Spatial Map into scene-shot images, ready for the Timeline.
        </p>
      </header>

      <ErsSelector
        sheets={sheets}
        selectedId={selectedSheetId}
        onSelected={setSelectedSheetId}
        disabled={busy}
      />

      {/* Placed entities from the Spatial Map */}
      <div data-testid="scene-creator-placed-entities" style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
        {characters.length ? (
          <div className="row" style={{ gap: "0.3rem", flexWrap: "wrap", alignItems: "center" }}>
            <span className="eyebrow" style={{ margin: 0 }}>Characters</span>
            {characters.map((c) => (
              <span
                key={c.character_id}
                className="library-media-grid__badge"
                style={{ padding: "0.15rem 0.4rem", borderRadius: "0.3rem", fontSize: "0.78rem" }}
                data-testid="scene-creator-character-chip"
              >
                @{c.name} <span className="muted">({c.position_label})</span>
              </span>
            ))}
          </div>
        ) : (
          <p className="muted" style={{ margin: 0, fontSize: "0.8rem" }}>
            No characters placed in the Spatial Map yet.
          </p>
        )}
        {props.length ? (
          <div className="row" style={{ gap: "0.3rem", flexWrap: "wrap", alignItems: "center" }}>
            <span className="eyebrow" style={{ margin: 0 }}>Props</span>
            {props.map((p) => (
              <span
                key={p.tag}
                className="library-media-grid__badge"
                style={{ padding: "0.15rem 0.4rem", borderRadius: "0.3rem", fontSize: "0.78rem" }}
                data-testid="scene-creator-prop-chip"
              >
                #{p.tag} <span className="muted">({p.position_label})</span>
              </span>
            ))}
          </div>
        ) : null}
      </div>

      {/* Output count + visual style */}
      <div className="row" style={{ gap: "0.75rem", flexWrap: "wrap", alignItems: "flex-end" }}>
        <label className="scene-meta" style={{ minWidth: "8rem" }}>
          Output Count
          <select
            value={outputCount}
            onChange={(e) => setOutputCount(Number(e.target.value))}
            disabled={busy}
            data-testid="scene-creator-output-count"
          >
            {OUTPUT_COUNT_OPTIONS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <label className="scene-meta" style={{ flex: "1 1 16rem", minWidth: "12rem" }}>
          Visual Style (optional)
          <input
            type="text"
            value={visualStyle}
            onChange={(e) => setVisualStyle(e.target.value)}
            disabled={busy}
            placeholder="e.g. cinematic, warm, film noir"
            data-testid="scene-creator-visual-style"
          />
        </label>
      </div>

      <ShotRequestInput
        projectId={projectId}
        value={shotText}
        onChange={setShotText}
        characters={characters}
        props={props}
        disabled={busy}
      />

      <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
        <p className="muted" style={{ margin: 0, fontSize: "0.8rem" }}>
          {batch ? `Most recent batch: ${batch.shot_requests.length} shot${batch.shot_requests.length === 1 ? "" : "s"}` : "No batches yet for this project."}
        </p>
        <button
          type="button"
          className="primary"
          onClick={() => void handleGenerate()}
          disabled={busy || !shotText.trim()}
          data-testid="scene-creator-generate"
        >
          {busy ? "Generating…" : "Generate Scene Images"}
        </button>
      </div>

      {error ? (
        <p className="muted" style={{ color: "var(--danger, #c33)", fontSize: "0.85rem" }} data-testid="scene-creator-error">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className="muted" style={{ color: "var(--good, #4a8)", fontSize: "0.85rem" }} data-testid="scene-creator-notice">
          {notice}
        </p>
      ) : null}

      {batch ? (
        <SceneResultGrid
          batch={batch}
          childJobs={childJobs}
          busy={busy}
          onRegenerateShot={(i) => void handleRegenerateShot(i)}
          onEditPrompt={(i, p) => void handleEditPrompt(i, p)}
          onSendShotToTimeline={(i) => void sendShotToTimeline(i)}
          sendingShotIndex={sendingShotIndex}
          onSendBatchToTimeline={() => void sendBatchToTimeline()}
          sendingBatchToTimeline={sendingBatch}
          onViewInLibrary={() => onGoTab?.("library")}
        />
      ) : null}
    </section>
  );
}
