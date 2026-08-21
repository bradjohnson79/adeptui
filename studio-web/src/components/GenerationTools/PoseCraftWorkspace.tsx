/**
 * PoseCraft production workspace — the single creator-facing PoseCraft experience.
 * Promoted PoseCraft v1.1 Babylon staging studio. Project-aware thin shell
 * hosting the Babylon viewport + panels. Landing/help = overlays only.
 * Persistence: per-project local draft key until the PoseCraft API lands.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { HelpTip, PanelHeading } from "../HelpTip";
import { Button } from "../ui";
import { api } from "../../api";
import { apiUrl } from "../../runtime/apiBase";
import {
  CAMERA_ASPECTS,
  CAMERA_GUIDES,
  CAMERA_PRESETS,
  FIGURE_ARCHETYPES,
  FIGURE_COLORS,
  FIGURE_ROLES,
  FURNITURE_PRESETS,
  JOINT_LABELS,
  POSECRAFT_LAYOUT_BOUNDS,
} from "../../posecraft/constants";
import { PoseCraftViewportController } from "../../posecraft/engine";
import type { GizmoMode, ManipulationEvent } from "../../posecraft/engine";
import {
  buildReferenceExport,
  buildSceneExport,
  downloadBlob,
} from "../../posecraft/exports";
import {
  POSE_CATALOG,
  POSE_CATEGORIES,
  getPoseById,
  isPoseCompatible,
} from "../../posecraft/poseCatalog";
import { renderPoseThumbnailSvg } from "../../posecraft/poseThumbnail";
import { buildSemanticSceneSummary } from "../../posecraft/semanticLabels";
import {
  addCustomFigureToScene,
  addFigure,
  addFurnitureToScene,
  addPrimitiveToScene,
  applyPosePreset,
  createDefaultDocument,
  createDefaultLayoutPrefs,
  createSnapshot,
  deleteSceneVersion,
  deleteSnapshot,
  duplicateFigure,
  duplicateSceneVersion,
  duplicateSnapshot,
  getSelectedSnapshot,
  POSECRAFT_SNAPSHOT_CAP,
  renameScene,
  renameSceneVersion,
  renameSnapshot,
  removeFigure,
  removePrimitiveFromScene,
  renameFigure,
  renamePrimitive,
  resetFigurePose,
  restoreSceneVersion,
  saveSceneVersion,
  selectFigure,
  selectJoint,
  selectPrimitive,
  selectSnapshot,
  setFigureRole,
  toggleStageFlag,
  updateCamera,
  updateFigure,
  updateFigureJoint,
  updatePrimitive,
  updateSceneNotes,
} from "../../posecraft/state";
import {
  analyzePoseIntelligence,
  comparePoseIntelligence,
  createCustomPose,
  deleteCustomPose,
  flushSceneDocument,
  handoffPoseToSceneCreator,
  handoffPoseToTimeline,
  listCustomPoses,
  loadPoseIntelligence,
  loadSceneDocument,
  saveSceneDocument,
  type PoseIntelligencePacket,
} from "../../posecraft/posecraftApi";
import type { ArchetypeId, FigureRole, FurnitureKind, PoseCategoryId, PoseCraftDocument, PoseCraftLayoutPrefs, PoseCraftScene, PoseMap, PosePreset } from "../../posecraft/types";
import type { Project } from "../../types";
import "../../posecraft/posecraft.css";
import "./posecraft-workspace.css";

const ASPECT_FRAME_WIDTHS: Record<string, string> = {
  "16:9": "88%", "2.39:1": "92%", "1:1": "56%", "4:5": "48%", "9:16": "34%",
};

type Props = {
  project: Project;
  onChange?: () => Promise<void>;
  onGo?: (tab: string) => void;
  onAskCoDirector?: (prompt?: string) => void;
};

function clampValue(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function Accordion({ id, label, open, onToggle, children }: {
  id: string; label: string; open: boolean; onToggle: () => void; children: React.ReactNode;
}) {
  return (
    <section className={`posecraft-accordion ${open ? "open" : "closed"}`} data-testid={`posecraft-accordion-${id}`}>
      <button type="button" className="posecraft-accordion-head" onClick={onToggle} aria-expanded={open} data-testid={`posecraft-accordion-toggle-${id}`}>
        <span className="posecraft-accordion-chevron" aria-hidden>{open ? "▾" : "▸"}</span>
        <span>{label}</span>
      </button>
      {open && <div className="posecraft-accordion-body">{children}</div>}
    </section>
  );
}

export function PoseCraftWorkspace({ project, onGo, onAskCoDirector }: Props) {
  // Master Program: the project API is the source of truth. We seed from a
  // default document synchronously (so the viewport can mount), then hydrate
  // from /api/posecraft/projects/:id/scene on mount. localStorage is no longer
  // the SoT — only favorites/undo remain client-side conveniences.
  const initialDocument = useMemo<PoseCraftDocument>(() => {
    const doc = createDefaultDocument();
    doc.currentScene.name = `${project.name} — PoseCraft Blocking`;
    return doc;
  }, [project.id, project.name]);

  const [documentState, setDocumentState] = useState<PoseCraftDocument>(initialDocument);
  const [history, setHistory] = useState(() => ({
    past: [] as PoseCraftScene[], present: initialDocument.currentScene, future: [] as PoseCraftScene[],
  }));
  const [hydrated, setHydrated] = useState(false);
  const [customPoses, setCustomPoses] = useState<PosePreset[]>([]);
  const [viewportStatus, setViewportStatus] = useState<{ renderer: "webgl" | "webgpu"; detail: string } | null>(null);
  const [poseCategory, setPoseCategory] = useState<PoseCategoryId | "all">("all");
  const [gizmoMode, setGizmoMode] = useState<GizmoMode>("move");
  const [poseSearch, setPoseSearch] = useState("");
  const [poseFavoritesOnly, setPoseFavoritesOnly] = useState(false);
  const [poseFavorites, setPoseFavorites] = useState<Set<string>>(() => {
    if (typeof window === "undefined") return new Set<string>();
    try {
      const raw = window.localStorage.getItem("adept.posecraft.favorites");
      return new Set<string>(raw ? JSON.parse(raw) : []);
    } catch {
      return new Set<string>();
    }
  });
  const [versionLabel, setVersionLabel] = useState("");
  const [statusMessage, setStatusMessage] = useState("PoseCraft is a staging studio. Nothing here leaves your browser until you send it on.");
  const [showIntro, setShowIntro] = useState(false);
  // Co-Director handoff: flush-then-open state so the button can show
  // loading/success/error feedback the creator can understand.
  const [sendingToCoDirector, setSendingToCoDirector] = useState(false);

  // Final Mandatory GO (D5–D6): per-row three-dot menu + inline rename state.
  const [openMenuFigureId, setOpenMenuFigureId] = useState<string | null>(null);
  const [renamingFigureId, setRenamingFigureId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [renamingPrimitiveId, setRenamingPrimitiveId] = useState<string | null>(null);
  const [primitiveRenameValue, setPrimitiveRenameValue] = useState("");
  // Version card ⋯ menu (Rename / Duplicate / Delete) — mirrors the Cast
  // figure three-dot menu pattern so the creator has consistent milestone
  // management without leaving the Versions + Exports accordion.
  const [openMenuVersionId, setOpenMenuVersionId] = useState<string | null>(null);
  const [renamingVersionId, setRenamingVersionId] = useState<string | null>(null);
  const [versionRenameValue, setVersionRenameValue] = useState("");

  // PoseCraft Snapshot gallery + handoff state. A Snapshot freezes one exact
  // camera composition for production handoff; it is NOT a scene save.
  const [capturingSnapshot, setCapturingSnapshot] = useState(false);
  // Transient flag that hides DOM camera guides + floating labels during a
  // clean PNG capture so the handoff image is a pure staging frame.
  const [capturingClean, setCapturingClean] = useState(false);
  const [openMenuSnapshotId, setOpenMenuSnapshotId] = useState<string | null>(null);
  const [renamingSnapshotId, setRenamingSnapshotId] = useState<string | null>(null);
  const [snapshotRenameValue, setSnapshotRenameValue] = useState("");
  const [previewSnapshotId, setPreviewSnapshotId] = useState<string | null>(null);
  const [sendingImageGen, setSendingImageGen] = useState(false);
  const [sendingStoryboard, setSendingStoryboard] = useState(false);
  const [sendingSceneCreator, setSendingSceneCreator] = useState(false);
  const [sendingTimeline, setSendingTimeline] = useState(false);
  const [poseIntelStatus, setPoseIntelStatus] = useState<"idle" | "analyzing" | "ready" | "warning" | "unavailable" | "degraded">("idle");
  const [poseIntel, setPoseIntel] = useState<PoseIntelligencePacket | null>(null);
  const [poseIntelDetail, setPoseIntelDetail] = useState("");
  const analyzeTimer = useRef<number | null>(null);
  const [viewportLabels, setViewportLabels] = useState<Array<{
    id: string; label: string; x: number; y: number; selected: boolean;
  }>>([]);

  // Gate A/B/I — layout prefs (persisted via the API document SoT).
  const layout = documentState.layoutPrefs ?? createDefaultLayoutPrefs();
  const [leftOpen, setLeftOpen] = useState<Set<string>>(() => new Set(layout.leftOpenAccordions));
  const [rightOpen, setRightOpen] = useState<Set<string>>(() => new Set(layout.rightOpenAccordions));
  const [fullscreen, setFullscreen] = useState(layout.fullscreen);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const controllerRef = useRef<PoseCraftViewportController | null>(null);
  const workspaceRef = useRef<HTMLDivElement | null>(null);
  const draggingDivider = useRef<"left" | "right" | null>(null);

  const scene = history.present;
  const currentDocument = useMemo(() => ({ ...documentState, currentScene: scene }), [documentState, scene]);
  // Refs mirror the latest scene/document so async handlers (e.g. mesh import)
  // flush the freshest state instead of a stale closure snapshot.
  const sceneRef = useRef(scene);
  sceneRef.current = scene;
  const documentRef = useRef(documentState);
  documentRef.current = documentState;
  // Tracks whether the creator mutated the scene before hydration finished,
  // so hydration can merge (not overwrite) those local additions.
  const localMutatedRef = useRef(false);
  // Mirrors the latest selection so the workspace keyboard handler always
  // reads the freshest selectedFigureId/selectedPrimitiveId without relying
  // on the effect re-binding timing (D6 furniture delete race).
  const selectedFigureIdRef = useRef(scene.selectedFigureId);
  selectedFigureIdRef.current = scene.selectedFigureId;
  const selectedPrimitiveIdRef = useRef(scene.selectedPrimitiveId ?? null);
  selectedPrimitiveIdRef.current = scene.selectedPrimitiveId ?? null;
  const selectedFigure = useMemo(
    () => scene.figures.find((figure) => figure.id === scene.selectedFigureId) ?? null,
    [scene],
  );
  const selectedJointRotation = selectedFigure?.pose[scene.selectedJoint] ?? { x: 0, y: 0, z: 0 };
  const allPosePresets = useMemo(() => [...POSE_CATALOG, ...customPoses], [customPoses]);

  const visiblePosePresets = useMemo(() => {
    const q = poseSearch.trim().toLowerCase();
    return allPosePresets.filter((preset) => {
      if (poseCategory !== "all" && preset.category !== poseCategory) return false;
      if (poseFavoritesOnly && !poseFavorites.has(preset.id)) return false;
      if (selectedFigure && !isPoseCompatible(preset, selectedFigure.archetypeId)) return false;
      if (!q) return true;
      return (
        preset.label.toLowerCase().includes(q) ||
        (preset.description ?? "").toLowerCase().includes(q) ||
        preset.id.toLowerCase().includes(q) ||
        preset.category.toLowerCase().includes(q)
      );
    });
  }, [allPosePresets, poseCategory, poseFavoritesOnly, poseFavorites, poseSearch, selectedFigure]);

  const toggleFavorite = useCallback((id: string) => {
    setPoseFavorites((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      if (typeof window !== "undefined") {
        window.localStorage.setItem("adept.posecraft.favorites", JSON.stringify([...next]));
      }
      return next;
    });
  }, []);

  // Master Program: save the selected figure's current pose as a project-scoped
  // custom pose via the API (CRUD). The thumbnail is generated from the pose's
  // canonical joint data so it always matches.
  const saveCurrentPoseAsCustom = useCallback(async () => {
    if (!selectedFigure) {
      setStatusMessage("Select a figure to save its pose.");
      return;
    }
    const label = window.prompt("Name this pose", "My Pose");
    if (!label) return;
    const poseId = `custom-${Date.now().toString(36)}`;
    const joints = selectedFigure.pose;
    const thumbnail = renderPoseThumbnailSvg(joints, { archetypeId: selectedFigure.archetypeId, color: "#0f766e", size: 96 });
    try {
      const record = await createCustomPose(project.id, {
        id: "pending",
        projectId: project.id,
        poseId,
        label,
        description: "Saved from PoseCraft viewport.",
        category: "custom",
        archetypes: [],
        joints,
        thumbnail,
        creatorModified: true,
        savedBy: "creator",
      });
      setCustomPoses((prev) => [
        ...prev,
        { id: record.poseId, label: record.label, category: "custom" as PoseCategoryId, description: record.description, archetypes: undefined, joints: record.joints as PoseMap, thumbnail: record.thumbnail },
      ]);
      setStatusMessage(`Saved "${label}" to this project's poses.`);
    } catch (error) {
      console.error(error);
      setStatusMessage("Could not save the custom pose to the server.");
    }
  }, [project.id, selectedFigure]);

  const removeCustomPose = useCallback(async (poseId: string) => {
    try {
      await deleteCustomPose(project.id, poseId);
      setCustomPoses((prev) => prev.filter((p) => p.id !== poseId));
      setStatusMessage("Removed the custom pose.");
    } catch (error) {
      console.error(error);
      setStatusMessage("Could not remove the custom pose.");
    }
  }, [project.id]);

  const aspectPreset = CAMERA_ASPECTS.find((entry) => entry.id === scene.camera.aspect) ?? CAMERA_ASPECTS[0];

  const commitScene = useCallback((nextScene: PoseCraftScene) => {
    setHistory((previous) =>
      Object.is(previous.present, nextScene)
        ? previous
        : { past: [...previous.past, previous.present].slice(-40), present: nextScene, future: [] },
    );
  }, []);
  const mutateScene = useCallback((mutator: (current: PoseCraftScene) => PoseCraftScene) => {
    setHistory((previous) => {
      const next = mutator(previous.present);
      if (Object.is(previous.present, next)) return previous;
      localMutatedRef.current = true;
      return { past: [...previous.past, previous.present].slice(-40), present: next, future: [] };
    });
  }, []);

  // Explicit cast menu actions (rename / duplicate / delete) and keyboard
  // deletes are commit gestures — the creator expects them to persist
  // immediately, not after the 600ms debounced auto-save. We update local
  // state AND flush the full document to the project API in the same tick
  // (same pattern as explicit Save Version). Refs keep this stable across
  // async gaps (e.g. mesh upload) so we always flush the freshest scene.
  const mutateAndFlush = useCallback((mutator: (current: PoseCraftScene) => PoseCraftScene) => {
    const next = mutator(sceneRef.current);
    if (Object.is(sceneRef.current, next)) return;
    localMutatedRef.current = true;
    setHistory((previous) =>
      Object.is(previous.present, next)
        ? previous
        : { past: [...previous.past, previous.present].slice(-40), present: next, future: [] },
    );
    const nextDocument = { ...documentRef.current, currentScene: next };
    flushSceneDocument(project.id, nextDocument).catch((error) => {
      console.error(error);
      setStatusMessage("Could not save this change to the server.");
    });
  }, [project.id]);

  // Flush the freshest local document immediately (keepalive so it survives
  // a tab tear-down). Used by inspector inputs on blur so a typed transform
  // lands on the server even if the creator reloads before the 600ms debounced
  // save fires — without relying on a global pagehide flush (which destabilized
  // the Beta proxy with connection resets).
  const flushNow = useCallback(() => {
    if (!localMutatedRef.current) return;
    const nextDocument = { ...documentRef.current, currentScene: sceneRef.current };
    flushSceneDocument(project.id, nextDocument).catch((error) => {
      console.error(error);
      setStatusMessage("Could not save this change to the server.");
    });
  }, [project.id]);

  // Final Mandatory GO (D5): cast three-dot menu actions.
  const startRenameFigure = useCallback((figureId: string, currentName: string) => {
    setRenamingFigureId(figureId);
    setRenameValue(currentName);
    setOpenMenuFigureId(null);
  }, []);

  const commitRenameFigure = useCallback(() => {
    if (!renamingFigureId) return;
    const finalName = renameValue.trim();
    mutateAndFlush((current) => renameFigure(current, renamingFigureId, finalName));
    setRenamingFigureId(null);
    setRenameValue("");
    setStatusMessage(finalName ? "Renamed figure." : "Figure name reset to archetype label.");
  }, [mutateAndFlush, renamingFigureId, renameValue]);

  const cancelRenameFigure = useCallback(() => {
    setRenamingFigureId(null);
    setRenameValue("");
  }, []);

  const duplicateFigureFromMenu = useCallback((figureId: string) => {
    mutateAndFlush((current) => duplicateFigure(current, figureId));
    setOpenMenuFigureId(null);
    setStatusMessage("Duplicated figure.");
  }, [mutateAndFlush]);

  const deleteFigureFromMenu = useCallback((figureId: string) => {
    mutateAndFlush((current) => removeFigure(current, figureId));
    setOpenMenuFigureId(null);
    setStatusMessage("Removed figure.");
  }, [mutateAndFlush]);

  // Version card ⋯ menu actions (Rename / Duplicate / Delete). These mutate
  // the document's savedVersions array (not the live scene), then flush the
  // full document to the project API so milestones persist across reload.
  // Mirrors the explicit Save Version flush pattern (keepalive PUT).
  const startRenameVersion = useCallback((versionId: string, currentLabel: string) => {
    setRenamingVersionId(versionId);
    setVersionRenameValue(currentLabel);
    setOpenMenuVersionId(null);
  }, []);

  const commitRenameVersion = useCallback(() => {
    if (!renamingVersionId) return;
    const finalLabel = versionRenameValue.trim();
    if (!finalLabel) {
      setRenamingVersionId(null);
      setVersionRenameValue("");
      return;
    }
    const nextDocument = renameSceneVersion(currentDocument, renamingVersionId, finalLabel);
    setDocumentState(nextDocument);
    setRenamingVersionId(null);
    setVersionRenameValue("");
    flushSceneDocument(project.id, nextDocument).catch((error) => {
      console.error(error);
      setStatusMessage("Could not save the renamed version to the server.");
    });
    setStatusMessage(`Renamed version to "${finalLabel}".`);
  }, [currentDocument, project.id, renamingVersionId, versionRenameValue]);

  const cancelRenameVersion = useCallback(() => {
    setRenamingVersionId(null);
    setVersionRenameValue("");
  }, []);

  const duplicateVersionFromMenu = useCallback((versionId: string) => {
    const nextDocument = duplicateSceneVersion(currentDocument, versionId);
    setDocumentState(nextDocument);
    setOpenMenuVersionId(null);
    flushSceneDocument(project.id, nextDocument).catch((error) => {
      console.error(error);
      setStatusMessage("Could not save the duplicated version to the server.");
    });
    setStatusMessage("Duplicated version.");
  }, [currentDocument, project.id]);

  const deleteVersionFromMenu = useCallback((versionId: string) => {
    const target = currentDocument.savedVersions.find((entry) => entry.id === versionId);
    const label = target?.label ?? "this version";
    if (!window.confirm(`Delete milestone "${label}"? This cannot be undone.`)) return;
    const nextDocument = deleteSceneVersion(currentDocument, versionId);
    setDocumentState(nextDocument);
    setOpenMenuVersionId(null);
    flushSceneDocument(project.id, nextDocument).catch((error) => {
      console.error(error);
      setStatusMessage("Could not save the deletion to the server.");
    });
    setStatusMessage(`Deleted milestone "${label}".`);
  }, [currentDocument, project.id]);

  // -------------------------------------------------------------------------
  // PoseCraft Snapshot — capture + gallery + handoff.
  //
  // Snapshot freezes one exact camera composition for production handoff. It
  // is NOT a scene save. The capture handler:
  //   1. Flushes the freshest scene to the project API (PUT). If the flush
  //      fails, the capture is BLOCKED — we never freeze a composition whose
  //      scene could not be persisted: "SNAPSHOT_BLOCKED — CURRENT POSECRAFT
  //      SCENE COULD NOT BE PERSISTED".
  //   2. Performs a CLEAN capture (gizmos / joint handles / selection outlines
  //      / floating labels / safe-margin & rule-of-thirds guides hidden).
  //   3. Uploads the PNG to the open project's Library (one project, one
  //      library — never a new project per snapshot).
  //   4. Appends a frozen Snapshot (camera/figures/primitives/semanticSummary
  //      deep-cloned at capture time), selects it, and flushes again so the
  //      selectedSnapshotId persists across reload.
  // -------------------------------------------------------------------------
  const applyPosePacket = useCallback((packet: PoseIntelligencePacket | null, fallbackReason = "") => {
    setPoseIntel(packet);
    if (!packet) {
      setPoseIntelStatus("unavailable");
      setPoseIntelDetail(fallbackReason || "Pose Intelligence is unavailable. Your pose is unchanged.");
      return;
    }
    const avail = packet.availability || "unavailable";
    if (avail === "unavailable") {
      setPoseIntelStatus("unavailable");
      setPoseIntelDetail(packet.reason || "Pose Intelligence is unavailable. Your pose is unchanged.");
      return;
    }
    if (avail === "degraded" || avail === "insufficient_reference") {
      setPoseIntelStatus((packet.warnings || []).length ? "warning" : "degraded");
      setPoseIntelDetail(
        [packet.creatorFacingDetails || packet.creatorFacingSummary, packet.reason].filter(Boolean).join(" "),
      );
      return;
    }
    setPoseIntelStatus((packet.warnings || []).length ? "warning" : "ready");
    setPoseIntelDetail(packet.creatorFacingDetails || packet.creatorFacingSummary || "");
  }, []);

  const runPoseAnalyze = useCallback(async (snapshotId?: string) => {
    setPoseIntelStatus("analyzing");
    try {
      const result = await analyzePoseIntelligence(project.id, {
        snapshotId: snapshotId || currentDocument.selectedSnapshotId || undefined,
        figureId: sceneRef.current.selectedFigureId || undefined,
      });
      applyPosePacket(result.packet);
    } catch (error) {
      console.error(error);
      applyPosePacket(null);
    }
  }, [applyPosePacket, currentDocument.selectedSnapshotId, project.id]);

  const runPoseContinuity = useCallback(async () => {
    const snaps = currentDocument.snapshots ?? [];
    if (snaps.length < 2) {
      setStatusMessage("Capture two Snapshots to check motion continuity.");
      return;
    }
    const selected = currentDocument.selectedSnapshotId || snaps[snaps.length - 1].snapshotId;
    const prior = snaps.filter((s) => s.snapshotId !== selected).at(-1);
    if (!prior) {
      setStatusMessage("Capture two Snapshots to check motion continuity.");
      return;
    }
    setPoseIntelStatus("analyzing");
    try {
      const result = await comparePoseIntelligence(project.id, prior.snapshotId, selected);
      applyPosePacket(result.to || null);
      const warnings = result.transition?.plausibilityWarnings || [];
      if (warnings.length) {
        setPoseIntelStatus("warning");
        setPoseIntelDetail(warnings[0]);
      }
      setStatusMessage(result.transition?.actionProgression || "Compared the two Snapshots.");
    } catch (error) {
      console.error(error);
      applyPosePacket(null);
    }
  }, [applyPosePacket, currentDocument.selectedSnapshotId, currentDocument.snapshots, project.id]);

  const captureSnapshotNow = useCallback(async () => {
    const controller = controllerRef.current;
    if (!controller) {
      setStatusMessage("Start the viewport before capturing a Snapshot.");
      return;
    }
    if (capturingSnapshot) return;
    setCapturingSnapshot(true);
    // Step 1 — flush the freshest scene. Never capture a composition whose
    // scene could not be persisted.
    const flushedDocument = { ...documentRef.current, currentScene: sceneRef.current };
    try {
      await flushSceneDocument(project.id, flushedDocument);
    } catch (error) {
      console.error(error);
      setCapturingSnapshot(false);
      setStatusMessage("SNAPSHOT_BLOCKED — CURRENT POSECRAFT SCENE COULD NOT BE PERSISTED");
      return;
    }
    // Step 2 — clean capture (hide DOM guides + labels, then engine hides
    // gizmos/handles/selection outlines).
    setCapturingClean(true);
    // Let React paint one frame with guides/labels hidden before capturing.
    await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()));
    let dataUrl = "";
    try {
      dataUrl = controller.captureCleanSnapshot();
    } finally {
      setCapturingClean(false);
    }
    if (!dataUrl) {
      setCapturingSnapshot(false);
      setStatusMessage("Could not capture a Snapshot image from the viewport.");
      return;
    }
    // Step 3 — upload the PNG to the open project's Library.
    let assetId = "";
    let assetFilename = "";
    try {
      const blob = await (await fetch(dataUrl)).blob();
      const file = new File([blob], `posecraft-snapshot-${Date.now()}.png`, { type: "image/png" });
      const asset = (await api.uploadAsset(project.id, file, "posecraft_snapshot", "image")) as { id: string; filename: string };
      assetId = asset.id;
      assetFilename = asset.filename;
    } catch (error) {
      console.error(error);
      setCapturingSnapshot(false);
      setStatusMessage("Could not upload the Snapshot image to the project Library.");
      return;
    }
    // Step 4 — append a frozen Snapshot, select it, flush again.
    const semanticSummary = buildSemanticSceneSummary(sceneRef.current);
    const baseDoc = { ...documentRef.current, currentScene: sceneRef.current };
    const { document: withSnapshot, snapshotId } = createSnapshot(
      baseDoc,
      project.id,
      assetId,
      semanticSummary,
    );
    setDocumentState(withSnapshot);
    try {
      await flushSceneDocument(project.id, withSnapshot);
    } catch (error) {
      console.error(error);
      setStatusMessage(`Saved Snapshot locally but could not persist it to the server (image: ${assetFilename}).`);
      setCapturingSnapshot(false);
      return;
    }
    setCapturingSnapshot(false);
    setStatusMessage(`Captured Snapshot for handoff (image stored in this project's Library).`);
    void runPoseAnalyze(snapshotId);
  }, [capturingSnapshot, project.id, runPoseAnalyze]);

  const startRenameSnapshot = useCallback((snapshotId: string, currentName: string) => {
    setRenamingSnapshotId(snapshotId);
    setSnapshotRenameValue(currentName);
    setOpenMenuSnapshotId(null);
  }, []);

  const commitRenameSnapshot = useCallback(() => {
    if (!renamingSnapshotId) return;
    const finalName = snapshotRenameValue.trim();
    if (!finalName) {
      setRenamingSnapshotId(null);
      setSnapshotRenameValue("");
      return;
    }
    const nextDocument = renameSnapshot(currentDocument, renamingSnapshotId, finalName);
    setDocumentState(nextDocument);
    setRenamingSnapshotId(null);
    setSnapshotRenameValue("");
    flushSceneDocument(project.id, nextDocument).catch((error) => {
      console.error(error);
      setStatusMessage("Could not save the renamed Snapshot to the server.");
    });
    setStatusMessage(`Renamed Snapshot to "${finalName}".`);
  }, [currentDocument, project.id, snapshotRenameValue, renamingSnapshotId]);

  const cancelRenameSnapshot = useCallback(() => {
    setRenamingSnapshotId(null);
    setSnapshotRenameValue("");
  }, []);

  const duplicateSnapshotFromMenu = useCallback((snapshotId: string) => {
    const nextDocument = duplicateSnapshot(currentDocument, snapshotId);
    setDocumentState(nextDocument);
    setOpenMenuSnapshotId(null);
    flushSceneDocument(project.id, nextDocument).catch((error) => {
      console.error(error);
      setStatusMessage("Could not save the duplicated Snapshot to the server.");
    });
    setStatusMessage("Duplicated Snapshot.");
  }, [currentDocument, project.id]);

  const deleteSnapshotFromMenu = useCallback((snapshotId: string) => {
    const target = (currentDocument.snapshots ?? []).find((s) => s.snapshotId === snapshotId);
    const name = target?.name ?? "this Snapshot";
    if (!window.confirm(`Delete Snapshot "${name}"? The frozen composition is removed; the project Library image stays.`)) return;
    const nextDocument = deleteSnapshot(currentDocument, snapshotId);
    setDocumentState(nextDocument);
    setOpenMenuSnapshotId(null);
    flushSceneDocument(project.id, nextDocument).catch((error) => {
      console.error(error);
      setStatusMessage("Could not save the Snapshot deletion to the server.");
    });
    setStatusMessage(`Deleted Snapshot "${name}".`);
  }, [currentDocument, project.id]);

  const selectSnapshotForHandoff = useCallback((snapshotId: string | null) => {
    // Toggle: clicking the already-selected card again deselects it (clears
    // the handoff selection). Clicking a different card selects that one.
    const currentSel = documentRef.current.selectedSnapshotId ?? null;
    const nextSel = currentSel === snapshotId ? null : snapshotId;
    const nextDocument = selectSnapshot(currentDocument, nextSel);
    setDocumentState(nextDocument);
    flushSceneDocument(project.id, nextDocument).catch((error) => {
      console.error(error);
      setStatusMessage("Could not save the Snapshot selection to the server.");
    });
  }, [currentDocument, project.id]);

  const restoreSnapshotCamera = useCallback((snapshotId: string) => {
    const snap = (currentDocument.snapshots ?? []).find((s) => s.snapshotId === snapshotId);
    if (!snap) return;
    setOpenMenuSnapshotId(null);
    // Restore ONLY the camera composition — NOT the full scene. Snapshot is a
    // frozen camera framing; restoring the camera lets the creator frame the
    // next shot from the same angle without overwriting their live staging.
    mutateScene((current) => updateCamera(current, snap.camera));
    setStatusMessage(`Restored the camera view from Snapshot "${snap.name}".`);
  }, [currentDocument.snapshots, mutateScene]);

  const exportSnapshotImage = useCallback((snapshotId: string) => {
    const snap = (currentDocument.snapshots ?? []).find((s) => s.snapshotId === snapshotId);
    if (!snap) return;
    setOpenMenuSnapshotId(null);
    // Download the frozen PNG capture from the project Library.
    const url = api.assetUrl(snap.imageAssetId);
    fetch(url, { credentials: "include" })
      .then((res) => (res.ok ? res.blob() : Promise.reject(new Error(`asset fetch ${res.status}`))))
      .then((blob) => {
        const a = document.createElement("a");
        const objectUrl = URL.createObjectURL(blob);
        a.href = objectUrl;
        a.download = `${snap.name.replace(/[^a-z0-9_-]+/gi, "_") || "posecraft-snapshot"}.png`;
        a.click();
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
        setStatusMessage(`Exported Snapshot "${snap.name}" as PNG.`);
      })
      .catch((error) => {
        console.error(error);
        setStatusMessage("Could not download the Snapshot image.");
      });
  }, [currentDocument.snapshots]);

  const selectedSnapshot = useMemo(() => getSelectedSnapshot(currentDocument), [currentDocument]);
  const hasSelectedSnapshot = Boolean(selectedSnapshot);
  const handoffDisabledTip = "Capture a Snapshot first to send this staging composition to production.";
  const snapshotCount = currentDocument.snapshots?.length ?? 0;

  // Final Mandatory GO (IMPORT): upload a mesh file into the open project's
  // Library and add it as a Custom Figure. Supports .obj/.gltf/.glb/.fbx. Does
  // NOT create a new project per import — reuses the current project id.
  const importCustomFigure = useCallback(async (file: File) => {
    const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
    if (!["obj", "gltf", "glb", "fbx"].includes(ext)) {
      setStatusMessage(`Unsupported file type: .${ext}. Use .obj, .gltf, .glb, or .fbx.`);
      return;
    }
    const formData = new FormData();
    formData.append("file", file);
    formData.append("tag", "posecraft-custom");
    formData.append("kind", "mesh-3d");
    try {
      const res = await fetch(apiUrl(`/api/projects/${project.id}/assets`), {
        method: "POST",
        credentials: "include",
        body: formData,
      });
      if (!res.ok) {
        setStatusMessage("Could not upload the custom figure to the project Library.");
        return;
      }
      const asset = await res.json() as { id: string; filename: string };
      mutateAndFlush((current) => addCustomFigureToScene(current, asset.id, asset.filename));
      setStatusMessage(`Imported "${asset.filename}" as a Custom Figure.`);
    } catch (error) {
      console.error(error);
      setStatusMessage("Could not import the custom figure.");
    }
  }, [mutateAndFlush, project.id]);

  // Final Mandatory GO (D6): workspace-level keyboard Delete/Backspace for
  // figures + furniture. Ignored when focus is in an input/textarea/content-
  // editable/search/numeric/rename field. Never deletes project / Character
  // profiles / Library / ERS. The handler reads selection from refs so it
  // always targets the freshest selection (no re-bind race after a click).
  useEffect(() => {
    function isEditableTarget(target: EventTarget | null): boolean {
      if (!(target instanceof HTMLElement)) return false;
      const tag = target.tagName.toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") return true;
      if (target.isContentEditable) return true;
      if (target.getAttribute("contenteditable") === "true") return true;
      return false;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Delete" && event.key !== "Backspace") return;
      if (isEditableTarget(event.target)) return;
      const figureId = selectedFigureIdRef.current;
      const primitiveId = selectedPrimitiveIdRef.current;
      if (figureId) {
        event.preventDefault();
        mutateAndFlush((current) => removeFigure(current, figureId));
        setStatusMessage("Removed figure (Delete).");
      } else if (primitiveId) {
        event.preventDefault();
        mutateAndFlush((current) => removePrimitiveFromScene(current, primitiveId));
        setStatusMessage("Removed furniture (Delete).");
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [mutateAndFlush]);

  // Master Program: in-viewport manipulation → canonical state. The engine
  // emits ManipulationEvent; this handler updates the canonical scene so the
  // round-trip is viewport → canonical → API save → reload → match.
  const handleManipulation = useCallback((event: ManipulationEvent) => {
    (globalThis as any).__pcManipulate = { kind: event.kind, figureId: (event as any).figureId, position: (event as any).position, count: ((globalThis as any).__pcManipulate?.count ?? 0) + 1 };
    if (event.kind === "select") {
      mutateScene((current) => ({ ...current, selectedFigureId: event.figureId }));
      return;
    }
    if (event.kind === "move") {
      mutateScene((current) => ({
        ...current,
        figures: current.figures.map((f) =>
          f.id === event.figureId ? { ...f, position: { ...f.position, x: event.position.x, z: event.position.z } } : f,
        ),
      }));
      setStatusMessage("Moved figure in viewport.");
      return;
    }
    if (event.kind === "rotate") {
      mutateScene((current) => ({
        ...current,
        figures: current.figures.map((f) =>
          f.id === event.figureId ? { ...f, rotationY: event.rotationY } : f,
        ),
      }));
      setStatusMessage("Rotated figure in viewport.");
      return;
    }
    if (event.kind === "pose") {
      mutateScene((current) => ({
        ...current,
        figures: current.figures.map((f) =>
          f.id === event.figureId
            ? { ...f, pose: { ...f.pose, [event.joint]: { x: event.rotation.x, y: event.rotation.y, z: event.rotation.z } } }
            : f,
        ),
      }));
      setStatusMessage(`Posed ${event.joint} in viewport.`);
    }
  }, [mutateScene]);

  // Apply accordion/fullscreen prefs from the API only once per project mount.
  // Re-applying after the creator (or Playwright) toggles an accordion races and
  // can silently close Furniture mid-interaction (Final GO FURN failure).
  const layoutPrefsAppliedRef = useRef(false);
  useEffect(() => {
    layoutPrefsAppliedRef.current = false;
    localMutatedRef.current = false;
  }, [project.id]);

  // Master Program: hydrate the document + custom poses from the project API
  // on mount. The API is the single source of truth (no localStorage SoT).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [doc, poses] = await Promise.all([
          loadSceneDocument(project.id),
          listCustomPoses(project.id).catch(() => []),
        ]);
        if (cancelled) return;
        try {
          const listed = await api.spatialMap.listMaps(project.id);
          const map = (listed as { documents?: Array<Record<string, unknown>> }).documents?.[0] as
            | { characters?: Array<{ label?: string; tag?: string; x?: number; y?: number; z?: number; positionMeters?: { x: number; y: number; z: number } }> }
            | undefined;
          const chars = map?.characters || [];
          if (chars.length && !doc.currentScene.worldOriginMeters) {
            const first = chars[0];
            const origin = first.positionMeters || { x: first.x || 0, y: first.y || 0, z: first.z || 0 };
            doc.currentScene.worldOriginMeters = origin;
            doc.currentScene.figures = doc.currentScene.figures.map((fig) => {
              const match = chars.find((c) => (c.label || c.tag || "").toLowerCase() === fig.name.toLowerCase());
              const meters = match?.positionMeters || (match ? { x: match.x || 0, y: match.y || 0, z: match.z || 0 } : null);
              if (!meters) return fig;
              if (Math.abs(fig.position.x) > 1e-6 || Math.abs(fig.position.z) > 1e-6) return fig;
              return { ...fig, position: { x: meters.x, z: meters.z } };
            });
          }
        } catch {
          /* Spatial Map origin is optional */
        }
        const prefs = doc.layoutPrefs ?? createDefaultLayoutPrefs();
        setDocumentState((prev) => ({ ...doc, savedVersions: doc.savedVersions ?? prev.savedVersions, layoutPrefs: prefs }));
        // Merge instead of overwrite: if the creator (or automation) added
        // figures/furniture before hydration finished, keep those local
        // additions on top of the authoritative API scene. Overwriting would
        // silently discard them (Final GO FURN race).
        setHistory((prev) => {
          if (!localMutatedRef.current) {
            return { ...prev, present: doc.currentScene };
          }
          const hydratedFigureIds = new Set(doc.currentScene.figures.map((f) => f.id));
          const localOnlyFigures = prev.present.figures.filter((f) => !hydratedFigureIds.has(f.id));
          const hydratedPrimIds = new Set(doc.currentScene.primitives.map((p) => p.id));
          const localOnlyPrimitives = prev.present.primitives.filter((p) => !hydratedPrimIds.has(p.id));
          return {
            ...prev,
            present: {
              ...doc.currentScene,
              figures: [...doc.currentScene.figures, ...localOnlyFigures],
              primitives: [...doc.currentScene.primitives, ...localOnlyPrimitives],
            },
          };
        });
        if (!layoutPrefsAppliedRef.current) {
          setLeftOpen(new Set(prefs.leftOpenAccordions));
          setRightOpen(new Set(prefs.rightOpenAccordions));
          setFullscreen(prefs.fullscreen);
          layoutPrefsAppliedRef.current = true;
        }
        setCustomPoses(
          poses.map((p) => ({
            id: p.poseId,
            label: p.label,
            category: (p.category as PoseCategoryId) ?? "custom",
            description: p.description,
            archetypes: (p.archetypes.length ? (p.archetypes as ArchetypeId[]) : undefined),
            joints: p.joints as PoseMap,
            thumbnail: p.thumbnail,
          })),
        );
        setHydrated(true);
      } catch (error) {
        if (cancelled) return;
        console.error(error);
        setStatusMessage("Could not load this project's PoseCraft scene from the server.");
        setHydrated(true);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  useEffect(() => {
    let cancelled = false;
    void loadPoseIntelligence(project.id).then((data) => {
      if (cancelled) return;
      if (data.packet) applyPosePacket(data.packet);
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [applyPosePacket, project.id]);

  useEffect(() => {
    if (!hydrated) return;
    if (analyzeTimer.current) window.clearTimeout(analyzeTimer.current);
    analyzeTimer.current = window.setTimeout(() => {
      void runPoseAnalyze(currentDocument.selectedSnapshotId || undefined);
    }, 900);
    return () => {
      if (analyzeTimer.current) window.clearTimeout(analyzeTimer.current);
    };
  }, [currentDocument.selectedSnapshotId, hydrated, runPoseAnalyze, scene.revision, scene.selectedFigureId]);

  // Debounced save to the project API (SoT). Skips the very first render until
  // hydration completes so we don't overwrite the server document with defaults.
  useEffect(() => {
    if (!hydrated) return;
    const handle = window.setTimeout(() => {
      saveSceneDocument(project.id, currentDocument).catch((error) => {
        console.error(error);
        setStatusMessage("Could not save this project's PoseCraft scene to the server.");
      });
    }, 600);
    return () => window.clearTimeout(handle);
  }, [currentDocument, project.id, hydrated]);

  // Gate I — persist layout prefs into the document whenever they change.
  useEffect(() => {
    if (!hydrated) return;
    setDocumentState((prev) => ({
      ...prev,
      layoutPrefs: {
        leftWidth: layout.leftWidth, rightWidth: layout.rightWidth,
        leftCollapsed: layout.leftCollapsed, rightCollapsed: layout.rightCollapsed,
        leftOpenAccordions: [...leftOpen], rightOpenAccordions: [...rightOpen], fullscreen,
      } as PoseCraftLayoutPrefs,
    }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leftOpen, rightOpen, fullscreen]);

  // Gate B — drag dividers (continuous, pointer-based, min/max bounded).
  useEffect(() => {
    function onMove(event: PointerEvent) {
      if (!draggingDivider.current || !workspaceRef.current) return;
      const rect = workspaceRef.current.getBoundingClientRect();
      const x = event.clientX - rect.left;
      if (draggingDivider.current === "left") {
        const next = clampValue(x, POSECRAFT_LAYOUT_BOUNDS.leftMin, POSECRAFT_LAYOUT_BOUNDS.leftMax);
        setDocumentState((prev) => ({ ...prev, layoutPrefs: { ...(prev.layoutPrefs ?? createDefaultLayoutPrefs()), leftWidth: next, leftCollapsed: false } }));
      } else if (draggingDivider.current === "right") {
        const fromRight = rect.width - x;
        const next = clampValue(fromRight, POSECRAFT_LAYOUT_BOUNDS.rightMin, POSECRAFT_LAYOUT_BOUNDS.rightMax);
        setDocumentState((prev) => ({ ...prev, layoutPrefs: { ...(prev.layoutPrefs ?? createDefaultLayoutPrefs()), rightWidth: next, rightCollapsed: false } }));
      }
    }
    function onUp() { draggingDivider.current = null; document.body.style.cursor = ""; }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("mousemove", onMove as EventListener);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("mousemove", onMove as EventListener);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!canvasRef.current) return;
    PoseCraftViewportController.create(canvasRef.current)
      .then((controller) => {
        if (cancelled) { controller.dispose(); return; }
        controllerRef.current = controller;
        setViewportStatus(controller.status);
        controller.setGizmoMode(gizmoMode);
        controller.onManipulate = handleManipulation;
        controller.sync(scene, scene.selectedFigureId);
        setShowIntro(false);
      })
      .catch((error: unknown) => {
        console.error(error);
        if (!cancelled) { setStatusMessage("PoseCraft could not start the 3D viewport on this browser."); setShowIntro(true); }
      });
    return () => { cancelled = true; controllerRef.current?.dispose(); controllerRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { controllerRef.current?.sync(scene, scene.selectedFigureId); }, [scene]);
  useEffect(() => { controllerRef.current?.setGizmoMode(gizmoMode); }, [gizmoMode]);
  useEffect(() => { controllerRef.current?.setSelectedFigure(scene.selectedFigureId); }, [scene.selectedFigureId]);

  // Co-Director scene labels — floating viewport labels track projected positions.
  useEffect(() => {
    if (!scene.stage.showLabels) {
      setViewportLabels([]);
      return;
    }
    let raf = 0;
    const tick = () => {
      const ctrl = controllerRef.current;
      if (ctrl) setViewportLabels(ctrl.getLabelScreenPositions(scene));
      raf = window.requestAnimationFrame(tick);
    };
    raf = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(raf);
  }, [scene]);

  // Final Mandatory GO (STORY): expose the current PoseCraft document on
  // window so the Playwright certification can read the staging package
  // (figures + furniture + camera) without poking the DOM.
  useEffect(() => {
    (globalThis as any).__posecraftDocument = currentDocument;
  }, [currentDocument]);

  const toggleLeft = useCallback((id: string) => {
    setLeftOpen((prev) => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  }, []);
  const toggleRight = useCallback((id: string) => {
    setRightOpen((prev) => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  }, []);
  const collapseLeft = useCallback(() => {
    setDocumentState((prev) => ({ ...prev, layoutPrefs: { ...(prev.layoutPrefs ?? createDefaultLayoutPrefs()), leftCollapsed: true } }));
  }, []);
  const expandLeft = useCallback(() => {
    setDocumentState((prev) => ({ ...prev, layoutPrefs: { ...(prev.layoutPrefs ?? createDefaultLayoutPrefs()), leftCollapsed: false } }));
  }, []);
  const collapseRight = useCallback(() => {
    setDocumentState((prev) => ({ ...prev, layoutPrefs: { ...(prev.layoutPrefs ?? createDefaultLayoutPrefs()), rightCollapsed: true } }));
  }, []);
  const expandRight = useCallback(() => {
    setDocumentState((prev) => ({ ...prev, layoutPrefs: { ...(prev.layoutPrefs ?? createDefaultLayoutPrefs()), rightCollapsed: false } }));
  }, []);
  const toggleFullscreen = useCallback(() => setFullscreen((v) => !v), []);

  const saveVersionNow = () => {
    const nextDocument = saveSceneVersion(currentDocument, versionLabel);
    setDocumentState(nextDocument);
    setVersionLabel("");
    // Explicit Save must persist to the server immediately — the debounced
    // auto-save would be cancelled by an immediate reload/navigation, losing
    // the scene (including labels). keepalive lets the PUT land even if the
    // creator reloads in the same tick as the click.
    flushSceneDocument(project.id, nextDocument).catch((error) => {
      console.error(error);
      setStatusMessage("Could not save this version to the server.");
    });
    setStatusMessage(`Saved ${nextDocument.savedVersions[0]?.label ?? "a new version"} to this project's draft.`);
  };
  const restoreVersionNow = (versionId: string) => {
    const nextDocument = restoreSceneVersion(currentDocument, versionId);
    setDocumentState(nextDocument);
    setHistory({ past: [], present: nextDocument.currentScene, future: [] });
    setStatusMessage("Restored a saved PoseCraft version.");
  };
  const useCurrentView = () => {
    const controllerState = controllerRef.current?.readCameraState();
    if (!controllerState) return;
    mutateScene((current) => updateCamera(current, controllerState));
    setStatusMessage("Captured the current viewport as the saved shot camera.");
  };

  // Final Mandatory GO (STORY): export the staging reference package
  // (figures + furniture + camera) for Image Generation / Storyboard.
  const exportStagingReference = () => {
    const renderer = viewportStatus?.renderer ?? "webgl";
    const snapshot = controllerRef.current?.captureSnapshot() ?? "";
    const blob = buildReferenceExport(currentDocument, renderer, snapshot);
    downloadBlob(blob, `${scene.name || "posecraft"}-staging-reference.json`);
    setStatusMessage("Exported the staging reference package.");
  };
  const exportSceneJson = () => {
    const renderer = viewportStatus?.renderer ?? "webgl";
    const blob = buildSceneExport(currentDocument, renderer);
    downloadBlob(blob, `${scene.name || "posecraft"}-scene.json`);
    setStatusMessage("Exported the PoseCraft scene JSON.");
  };

  // Co-Director handoff: flush the freshest scene to the project API so
  // Co-Director's posecraft.inspect_scene tool reads the live blocking (not
  // a stale debounced snapshot), then open the Co-Director session with a
  // creator-facing prompt that asks it to review the staged scene. One
  // project, one library — we never spawn a new project; Co-Director reads
  // the scene from the SAME projectId via the frozen posecraft.* contracts.
  //
  // Snapshot gating: a Snapshot freezes one exact camera composition for
  // production handoff. Send to Co-Director is the FIRST handoff action and
  // requires a selected Snapshot. The prompt references the Snapshot by name
  // + asset + revision and uses creator labels (not staging colors).
  const sendToCoDirector = useCallback(async () => {
    if (!onAskCoDirector) {
      setStatusMessage("Co-Director is not available right now.");
      return;
    }
    const snap = getSelectedSnapshot(documentRef.current);
    if (!snap) {
      setStatusMessage(handoffDisabledTip);
      return;
    }
    setSendingToCoDirector(true);
    const nextDocument = { ...documentRef.current, currentScene: sceneRef.current };
    try {
      await flushSceneDocument(project.id, nextDocument);
    } catch (error) {
      console.error(error);
      setSendingToCoDirector(false);
      setStatusMessage("Could not save the scene before opening Co-Director. Try again.");
      return;
    }
    const sceneName = sceneRef.current.name || "this scene";
    const figureCount = snap.figures.length;
    const furnitureCount = snap.primitives.length;
    const lensMm = snap.camera.lensMm;
    const aspect = snap.camera.aspect;
    const figureNames = snap.figures.map((f) => f.name).filter(Boolean).slice(0, 8).join(", ");
    const prompt =
      `I captured a PoseCraft Snapshot "${snap.name}" for "${sceneName}" ` +
      `(revision ${snap.sceneRevision}, ${lensMm}mm, ${aspect})` +
      (figureCount ? ` — ${figureCount} figure${figureCount === 1 ? "" : "s"}` : " — no figures") +
      (figureNames ? ` (${figureNames})` : "") +
      (furnitureCount ? `, ${furnitureCount} prop${furnitureCount === 1 ? "" : "s"}` : "") +
      `. The Snapshot image is stored in this project's Library (asset ${snap.imageAssetId}). ` +
      `Use posecraft.inspect_scene with snapshotId "${snap.snapshotId}" to read the frozen composition, ` +
      `then give me director notes on composition, eyelines, and camera. ` +
      `Treat it as a PoseCraft Snapshot — Visual Staging Reference, not a final frame. ` +
      `Describe figures by their labels and roles, not by staging color.`;
    try {
      onAskCoDirector(prompt);
      setStatusMessage("Sent the PoseCraft Snapshot to Co-Director. Open the Co-Director panel to continue.");
    } catch (error) {
      console.error(error);
      setStatusMessage("Could not open Co-Director. Try again.");
    } finally {
      setSendingToCoDirector(false);
    }
  }, [handoffDisabledTip, onAskCoDirector, project.id]);

  // Image Generation handoff: project-scoped so the reference thumbnail
  // appears. Requires a selected Snapshot. Seeds the Image Gen tab with the
  // frozen Snapshot asset so the creator sees the staging reference there.
  const sendToImageGeneration = useCallback(async () => {
    if (sendingImageGen) return;
    const snap = getSelectedSnapshot(documentRef.current);
    if (!snap) {
      setStatusMessage(handoffDisabledTip);
      return;
    }
    setSendingImageGen(true);
    try {
      // Project-scoped handoff: stash the frozen Snapshot reference so the
      // Image Gen tab can show the staging thumbnail on open (existing
      // sessionStorage handoff pattern).
      try {
        window.sessionStorage.setItem(
          `adept.posecraft.handoff.${project.id}`,
          JSON.stringify({
            snapshotId: snap.snapshotId,
            imageAssetId: snap.imageAssetId,
            name: snap.name,
            sceneRevision: snap.sceneRevision,
            lensMm: snap.camera.lensMm,
            aspect: snap.camera.aspect,
            honestyLabel: "PoseCraft Snapshot — Visual Staging Reference",
            at: Date.now(),
          }),
        );
      } catch {
        /* sessionStorage may be unavailable; handoff still proceeds via onGo */
      }
      onGo?.("imagegen");
      setStatusMessage(`Sent Snapshot "${snap.name}" to Image Generation.`);
    } finally {
      setSendingImageGen(false);
    }
  }, [handoffDisabledTip, onGo, project.id, sendingImageGen]);

  // Storyboard handoff: requires a selected Snapshot.
  const sendToStoryboard = useCallback(async () => {
    if (sendingStoryboard) return;
    const snap = getSelectedSnapshot(documentRef.current);
    if (!snap) {
      setStatusMessage(handoffDisabledTip);
      return;
    }
    setSendingStoryboard(true);
    try {
      try {
        window.sessionStorage.setItem(
          `adept.posecraft.storyboard.${project.id}`,
          JSON.stringify({
            snapshotId: snap.snapshotId,
            imageAssetId: snap.imageAssetId,
            name: snap.name,
            sceneRevision: snap.sceneRevision,
            honestyLabel: "PoseCraft Snapshot — Visual Staging Reference",
            at: Date.now(),
          }),
        );
      } catch {
        /* ignore */
      }
      onGo?.("script");
      setStatusMessage(`Sent Snapshot "${snap.name}" to Storyboard.`);
    } finally {
      setSendingStoryboard(false);
    }
  }, [handoffDisabledTip, onGo, project.id, sendingStoryboard]);

  const sendToSceneCreator = useCallback(async () => {
    const snap = getSelectedSnapshot(documentRef.current);
    if (!snap) {
      setStatusMessage(handoffDisabledTip);
      return;
    }
    setSendingSceneCreator(true);
    try {
      await flushSceneDocument(project.id, { ...documentRef.current, currentScene: sceneRef.current });
      await handoffPoseToSceneCreator(project.id, snap.snapshotId);
      try {
        window.sessionStorage.setItem(
          `adept.posecraft.scenecreator.${project.id}`,
          JSON.stringify({ snapshotId: snap.snapshotId, imageAssetId: snap.imageAssetId, name: snap.name, at: Date.now() }),
        );
      } catch { /* ignore */ }
      onGo?.("scenecreator");
      setStatusMessage(`Sent Snapshot "${snap.name}" and pose notes to Scene Creator.`);
    } catch (error) {
      console.error(error);
      setStatusMessage("Could not send pose notes to Scene Creator. Your pose is unchanged.");
    } finally {
      setSendingSceneCreator(false);
    }
  }, [handoffDisabledTip, onGo, project.id]);

  const sendToTimeline = useCallback(async () => {
    const snap = getSelectedSnapshot(documentRef.current);
    if (!snap) {
      setStatusMessage(handoffDisabledTip);
      return;
    }
    setSendingTimeline(true);
    try {
      await flushSceneDocument(project.id, { ...documentRef.current, currentScene: sceneRef.current });
      await handoffPoseToTimeline(project.id, snap.snapshotId);
      try {
        window.sessionStorage.setItem(
          `adept.posecraft.timeline.${project.id}`,
          JSON.stringify({ snapshotId: snap.snapshotId, imageAssetId: snap.imageAssetId, name: snap.name, at: Date.now() }),
        );
      } catch { /* ignore */ }
      onGo?.("timeline");
      setStatusMessage(`Sent Snapshot "${snap.name}" and motion notes to Timeline.`);
    } catch (error) {
      console.error(error);
      setStatusMessage("Could not send motion notes to Timeline. Your pose is unchanged.");
    } finally {
      setSendingTimeline(false);
    }
  }, [handoffDisabledTip, onGo, project.id]);

  return (
    <div className="page posecraft-workspace" data-testid="posecraft-workspace">
      <header className="posecraft-workspace__header">
        <div>
          <p className="posecraft-workspace__eyebrow">
            PoseCraft
            <span className="posecraft-workspace__pill" data-testid="posecraft-production-pill">Production</span>
          </p>
          <h2 className="posecraft-workspace__title">Block your scene in 3D</h2>
          <p className="muted posecraft-workspace__subtitle">
            Pose characters, set the camera, then send the staging reference to Image Generation.
          </p>
        </div>
        <div className="posecraft-workspace__actions">
          <Button variant="secondary" onClick={() => onGo?.("characters")} data-testid="posecraft-open-characters">
            Open Character Creator
          </Button>
          <Button variant="primary" onClick={() => onGo?.("imagegen")} data-testid="posecraft-open-imagegen">
            Send to Image Generation
          </Button>
        </div>
      </header>
      <p className="scene-meta" data-testid="posecraft-status-message">{statusMessage}</p>

      <section
        className={`posecraft-shell ${fullscreen ? "posecraft-shell--fullscreen" : ""}`}
        data-testid="posecraft-shell"
        ref={workspaceRef}
      >
        {!fullscreen && !layout.leftCollapsed && (
          <aside
            className="panel posecraft-pane posecraft-pane--left"
            data-testid="posecraft-figure-browser"
            style={{ width: layout.leftWidth }}
          >
            <div className="posecraft-pane-scroll" data-testid="posecraft-left-scroll">
            <Accordion id="cast" label="Cast" open={leftOpen.has("cast")} onToggle={() => toggleLeft("cast")}>
              <PanelHeading title="Cast Browser" tip="Add low-poly stand-ins fast, then pick the one you want to direct." />
              <div className="posecraft-archetype-grid">
                {FIGURE_ARCHETYPES.map((archetype) => (
                  <button key={archetype.id} type="button" data-testid={`posecraft-add-${archetype.id}`}
                    onClick={() => { mutateScene((current) => addFigure(current, archetype.id)); setStatusMessage(`Added ${archetype.label}.`); }}>
                    <strong>{archetype.label}</strong>
                    <span>{archetype.height.toFixed(2)}m base</span>
                  </button>
                ))}
              </div>
              <div className="posecraft-figure-list" data-testid="posecraft-figure-list">
                {scene.figures.map((figure) => {
                  const archetypeLabel = FIGURE_ARCHETYPES.find((entry) => entry.id === figure.archetypeId)?.label ?? figure.archetypeId;
                  const colorHex = FIGURE_COLORS.find((entry) => entry.id === figure.colorId)?.hex ?? "#0f766e";
                  const isSelected = scene.selectedFigureId === figure.id;
                  const isRenaming = renamingFigureId === figure.id;
                  const menuOpen = openMenuFigureId === figure.id;
                  return (
                    <div
                      key={figure.id}
                      className={`posecraft-figure-row ${isSelected ? "selected" : ""}`}
                      data-testid={`posecraft-figure-row-${figure.id}`}
                    >
                      <button
                        type="button"
                        className="posecraft-figure-row-main"
                        onClick={() => commitScene(selectFigure(scene, figure.id))}
                      >
                        <span className="posecraft-color-dot" style={{ background: colorHex }} aria-hidden />
                        {isRenaming ? (
                          <input
                            autoFocus
                            value={renameValue}
                            data-testid={`posecraft-figure-rename-${figure.id}`}
                            onChange={(event) => setRenameValue(event.target.value)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter") { event.preventDefault(); commitRenameFigure(); }
                              else if (event.key === "Escape") { event.preventDefault(); cancelRenameFigure(); }
                            }}
                            onBlur={() => commitRenameFigure()}
                          />
                        ) : (
                          <div className="posecraft-figure-row-text">
                            <strong>{figure.name}</strong>
                            <span>
                              {archetypeLabel}
                              {figure.role && figure.role !== "unspecified"
                                ? ` · ${FIGURE_ROLES.find((r) => r.id === figure.role)?.label ?? figure.role}`
                                : ""}
                            </span>
                            <span>Position: {figure.position.x.toFixed(1)}, 0, {figure.position.z.toFixed(1)}</span>
                          </div>
                        )}
                      </button>
                      <button
                        type="button"
                        className="posecraft-figure-row-menu"
                        data-testid={`posecraft-figure-menu-${figure.id}`}
                        aria-label="Figure actions"
                        onClick={(event) => {
                          event.stopPropagation();
                          setOpenMenuFigureId(menuOpen ? null : figure.id);
                        }}
                      >…</button>
                      {menuOpen && (
                        <div className="posecraft-figure-menu-popover" data-testid={`posecraft-figure-popover-${figure.id}`}>
                          <button type="button" data-testid={`posecraft-figure-rename-btn-${figure.id}`}
                            onClick={() => startRenameFigure(figure.id, figure.name)}>Rename</button>
                          <button type="button" data-testid={`posecraft-figure-duplicate-btn-${figure.id}`}
                            onClick={() => duplicateFigureFromMenu(figure.id)}>Duplicate</button>
                          <button type="button" className="danger" data-testid={`posecraft-figure-delete-btn-${figure.id}`}
                            onClick={() => deleteFigureFromMenu(figure.id)}>Delete</button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              {/* Final Mandatory GO (IMPORT): Custom Figures section. */}
              <div className="posecraft-custom-figures-section" data-testid="posecraft-custom-figures">
                <PanelHeading title="Custom Figures" tip="Import your own .obj, .gltf, .glb, or .fbx mesh. Custom figures support Move / Rotate / Scale only — no skeletal pose." />
                <label className="posecraft-field">
                  <span>Import mesh</span>
                  <input
                    type="file"
                    accept=".obj,.gltf,.glb,.fbx"
                    data-testid="posecraft-custom-import-input"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) importCustomFigure(file);
                      event.target.value = "";
                    }}
                  />
                </label>
                <p className="muted">Imported meshes are stored in this project's Library and listed here.</p>
                <div className="posecraft-figure-list">
                  {scene.figures.filter((f) => f.kind === "custom").map((figure) => {
                    const colorHex = FIGURE_COLORS.find((entry) => entry.id === figure.colorId)?.hex ?? "#0f766e";
                    const isSelected = scene.selectedFigureId === figure.id;
                    const menuOpen = openMenuFigureId === figure.id;
                    return (
                      <div key={figure.id} className={`posecraft-figure-row ${isSelected ? "selected" : ""}`} data-testid={`posecraft-custom-row-${figure.id}`}>
                        <button type="button" className="posecraft-figure-row-main" onClick={() => commitScene(selectFigure(scene, figure.id))}>
                          <span className="posecraft-color-dot" style={{ background: colorHex }} aria-hidden />
                          <div className="posecraft-figure-row-text">
                            <strong>{figure.name}</strong>
                            <span>Custom Figure</span>
                            <span>Position: {figure.position.x.toFixed(1)}, 0, {figure.position.z.toFixed(1)}</span>
                          </div>
                        </button>
                        <button type="button" className="posecraft-figure-row-menu" data-testid={`posecraft-custom-menu-${figure.id}`}
                          onClick={(event) => { event.stopPropagation(); setOpenMenuFigureId(menuOpen ? null : figure.id); }}>…</button>
                        {menuOpen && (
                          <div className="posecraft-figure-menu-popover" data-testid={`posecraft-custom-popover-${figure.id}`}>
                            <button type="button" data-testid={`posecraft-custom-rename-btn-${figure.id}`} onClick={() => startRenameFigure(figure.id, figure.name)}>Rename</button>
                            <button type="button" data-testid={`posecraft-custom-duplicate-btn-${figure.id}`} onClick={() => duplicateFigureFromMenu(figure.id)}>Duplicate</button>
                            <button type="button" className="danger" data-testid={`posecraft-custom-delete-btn-${figure.id}`} onClick={() => deleteFigureFromMenu(figure.id)}>Delete</button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </Accordion>

            <Accordion id="pose-library" label="Pose Library" open={leftOpen.has("pose-library")} onToggle={() => toggleLeft("pose-library")}>
              <div className="posecraft-pose-controls posecraft-pose-controls--sticky" data-testid="posecraft-pose-controls">
            <input
              type="search"
              placeholder="Search poses…"
              value={poseSearch}
              data-testid="posecraft-pose-search"
              onChange={(event) => setPoseSearch(event.target.value)}
            />
            <select value={poseCategory} data-testid="posecraft-pose-category"
              onChange={(event) => setPoseCategory(event.target.value as PoseCategoryId | "all")}>
              {POSE_CATEGORIES.map((cat) => (<option key={cat.id} value={cat.id}>{cat.label}</option>))}
            </select>
            <button type="button"
              className={poseFavoritesOnly ? "primary" : ""}
              data-testid="posecraft-pose-favorites"
              onClick={() => setPoseFavoritesOnly((v) => !v)}>
              {poseFavoritesOnly ? "★ Favorites" : "☆ Favorites"}
            </button>
            <button type="button"
              disabled={!selectedFigure}
              data-testid="posecraft-save-custom-pose"
              onClick={saveCurrentPoseAsCustom}
              title="Save the selected figure's current pose to this project">
              + Save pose
            </button>
          </div>
          <p className="posecraft-pose-count" data-testid="posecraft-pose-count">
            {visiblePosePresets.length} of {allPosePresets.length} poses
          </p>
          <div className="posecraft-pose-list posecraft-pose-scroll" data-testid="posecraft-pose-library">
            {visiblePosePresets.map((preset) => {
              const fav = poseFavorites.has(preset.id);
              return (
                <button key={preset.id} type="button" disabled={!selectedFigure}
                  className="posecraft-pose-card"
                  data-testid={`posecraft-pose-${preset.id}`}
                  onClick={() => {
                    if (!selectedFigure) return;
                    const resolved = getPoseById(preset.id) ?? customPoses.find((p) => p.id === preset.id);
                    if (!resolved) return;
                    mutateScene((current) => applyPosePreset(current, selectedFigure.id, resolved));
                    setStatusMessage(`Applied ${preset.label}.`);
                  }}>
                  <span className="posecraft-pose-thumb" dangerouslySetInnerHTML={{ __html: preset.thumbnail ?? "" }} />
                  <span className="posecraft-pose-meta">
                    <strong>{preset.label}</strong>
                    <span>{preset.description}</span>
                  </span>
                  <span
                    className="posecraft-pose-fav"
                    data-testid={`posecraft-pose-fav-${preset.id}`}
                    role="button"
                    aria-label={fav ? "Remove favorite" : "Add favorite"}
                    onClick={(event) => { event.stopPropagation(); toggleFavorite(preset.id); }}>
                    {fav ? "★" : "☆"}
                  </span>
                  {!getPoseById(preset.id) && (
                    <span
                      className="posecraft-pose-del"
                      data-testid={`posecraft-pose-del-${preset.id}`}
                      role="button"
                      aria-label="Delete custom pose"
                      onClick={(event) => { event.stopPropagation(); removeCustomPose(preset.id); }}>
                      ✕
                    </span>
                  )}
                </button>
              );
            })}
            {visiblePosePresets.length === 0 && (<p className="empty">No poses match this filter.</p>)}
          </div>
            </Accordion>

            <Accordion id="furniture" label="Furniture" open={leftOpen.has("furniture")} onToggle={() => toggleLeft("furniture")}>
              <p className="muted">Drop simple blocking furniture onto the stage.</p>
              <div className="posecraft-furniture-grid" data-testid="posecraft-furniture-grid">
                {FURNITURE_PRESETS.map((preset) => (
                  <button key={preset.kind} type="button" data-testid={`posecraft-add-furniture-${preset.kind}`}
                    onClick={() => { mutateScene((current) => addFurnitureToScene(current, preset.kind as FurnitureKind)); setStatusMessage(`Added ${preset.label}.`); }}>
                    <strong>{preset.label}</strong>
                    <span>{preset.description}</span>
                  </button>
                ))}
              </div>
              <div className="posecraft-primitive-list" data-testid="posecraft-primitive-list">
                {scene.primitives.map((primitive) => {
                  const isSel = scene.selectedPrimitiveId === primitive.id;
                  const isRenaming = renamingPrimitiveId === primitive.id;
                  return (
                    <div key={primitive.id}
                      className={`posecraft-primitive-card ${isSel ? "selected" : ""}`}
                      data-testid={`posecraft-primitive-card-${primitive.id}`}
                      onClick={() => commitScene(selectPrimitive(scene, primitive.id))}
                      onDoubleClick={(event) => {
                        event.stopPropagation();
                        setRenamingPrimitiveId(primitive.id);
                        setPrimitiveRenameValue(primitive.name);
                      }}>
                      {isRenaming ? (
                        <input
                          autoFocus
                          value={primitiveRenameValue}
                          data-testid={`posecraft-primitive-rename-${primitive.id}`}
                          onClick={(event) => event.stopPropagation()}
                          onChange={(event) => setPrimitiveRenameValue(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter") {
                              event.preventDefault();
                              mutateScene((current) => renamePrimitive(current, primitive.id, primitiveRenameValue));
                              setRenamingPrimitiveId(null);
                            } else if (event.key === "Escape") {
                              event.preventDefault();
                              setRenamingPrimitiveId(null);
                            }
                          }}
                          onBlur={() => {
                            mutateScene((current) => renamePrimitive(current, primitive.id, primitiveRenameValue));
                            setRenamingPrimitiveId(null);
                          }}
                        />
                      ) : (
                        <strong>{primitive.name}</strong>
                      )}
                      <span className="muted">{primitive.kind}</span>
                      <div className="posecraft-field-grid">
                        <label className="posecraft-field"><span>X</span>
                          <input type="number" step="0.1" value={primitive.position.x}
                            onChange={(event) => mutateScene((current) => updatePrimitive(current, primitive.id, { position: { ...primitive.position, x: Number(event.target.value) } }))} />
                        </label>
                        <label className="posecraft-field"><span>Z</span>
                          <input type="number" step="0.1" value={primitive.position.z}
                            onChange={(event) => mutateScene((current) => updatePrimitive(current, primitive.id, { position: { ...primitive.position, z: Number(event.target.value) } }))} />
                        </label>
                      </div>
                      <button type="button" className="ghost" data-testid={`posecraft-primitive-rename-btn-${primitive.id}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          setRenamingPrimitiveId(primitive.id);
                          setPrimitiveRenameValue(primitive.name);
                        }}>Rename</button>
                      <button type="button" className="ghost" data-testid={`posecraft-primitive-remove-${primitive.id}`}
                        onClick={(event) => { event.stopPropagation(); mutateScene((current) => removePrimitiveFromScene(current, primitive.id)); }}>Remove</button>
                    </div>
                  );
                })}
              </div>
            </Accordion>

            <Accordion id="scene" label="Scene" open={leftOpen.has("scene")} onToggle={() => toggleLeft("scene")}>
              <div className="posecraft-toolbar" data-testid="posecraft-toolbar">
                <label className="posecraft-field">
                  <span>Scene Name</span>
                  <input data-testid="posecraft-scene-name" value={scene.name}
                    onChange={(event) => mutateScene((current) => renameScene(current, event.target.value))} />
                </label>
                <label className="posecraft-field">
                  <span>Director Notes</span>
                  <input data-testid="posecraft-scene-notes" value={scene.notes}
                    onChange={(event) => mutateScene((current) => updateSceneNotes(current, event.target.value))} />
                </label>
                <div className="posecraft-toolbar-actions">
                  <button type="button" data-testid="posecraft-undo"
                    onClick={() => setHistory((p) => p.past.length ? { past: p.past.slice(0, -1), present: p.past[p.past.length - 1]!, future: [p.present, ...p.future] } : p)}
                    disabled={!history.past.length}>Undo</button>
                  <button type="button" data-testid="posecraft-redo"
                    onClick={() => setHistory((p) => p.future.length ? { past: [...p.past, p.present], present: p.future[0]!, future: p.future.slice(1) } : p)}
                    disabled={!history.future.length}>Redo</button>
                </div>
              </div>
            </Accordion>
            </div>

            <button type="button" className="posecraft-pane-collapse" data-testid="posecraft-collapse-left" onClick={collapseLeft}>◂ Hide Cast</button>
          </aside>
        )}
        {!fullscreen && !layout.leftCollapsed && (
          <div className="posecraft-divider" data-testid="posecraft-divider-left"
            onPointerDown={(event) => { draggingDivider.current = "left"; document.body.style.cursor = "col-resize"; (document.body as any).dataset.dividerDragging = "left"; event.preventDefault(); }}
            onMouseDown={(event) => { draggingDivider.current = "left"; document.body.style.cursor = "col-resize"; (document.body as any).dataset.dividerDragging = "left"; event.preventDefault(); }} />
        )}
        {!fullscreen && layout.leftCollapsed && (
          <button type="button" className="posecraft-edge-tab posecraft-edge-tab--left" data-testid="posecraft-expand-left" onClick={expandLeft}>▸</button>
        )}

        <section className="panel posecraft-viewport-pane" data-testid="posecraft-viewport-panel">
          <PanelHeading title="Viewport" tip="Orbit, pan, and zoom the neutral stage. Figures and props stay snapped to the floor.">
            <div className="timeline-header-badges">
              <span className="pill" data-testid="posecraft-renderer-pill">{viewportStatus ? viewportStatus.detail : "Starting viewport…"}</span>
              <span className="pill">Ground snap</span>
            </div>
          </PanelHeading>
          <div className="posecraft-stage-actions">
            <div className="posecraft-gizmo-group" role="group" aria-label="Manipulation mode" data-testid="posecraft-gizmo-mode">
              <button type="button" className={gizmoMode === "move" ? "primary" : ""} data-testid="posecraft-gizmo-move"
                title="Move the whole figure — drag the figure across the stage floor"
                onClick={() => setGizmoMode("move")}>Move</button>
              <button type="button" className={gizmoMode === "rotate" ? "primary" : ""} data-testid="posecraft-gizmo-rotate"
                title="Rotate the whole figure — turn the entire character (figure yaw). For body-part posing, use Pose Body."
                onClick={() => setGizmoMode("rotate")}>Rotate figure</button>
              <button type="button" className={gizmoMode === "pose" ? "primary" : ""} data-testid="posecraft-gizmo-pose"
                title="Pose body parts — rotate individual joints (head, arms, spine, legs). To turn the whole character, use Rotate figure."
                onClick={() => setGizmoMode("pose")}>Pose body</button>
              <button type="button" data-testid="posecraft-gizmo-camera"
                title="Camera — orbit, pan, and zoom the view"
                onClick={() => setGizmoMode("move")}>Camera</button>
            </div>
            <button type="button" data-testid="posecraft-add-primitive" title="Add Blocking Box"
              onClick={() => { mutateScene((current) => addPrimitiveToScene(current)); setStatusMessage("Added a simple blocking box."); }}>Add Box</button>
            <button
              type="button"
              className={scene.stage.showLabels ? "primary" : ""}
              data-testid="posecraft-show-labels"
              aria-pressed={Boolean(scene.stage.showLabels)}
              title="Show Labels"
              onClick={() => mutateScene((current) => toggleStageFlag(current, "showLabels"))}
            >
              Labels
            </button>
            <button type="button" onClick={useCurrentView} data-testid="posecraft-use-view" title="Use Current View">Use View</button>
            <button
              type="button"
              onClick={captureSnapshotNow}
              disabled={capturingSnapshot}
              data-testid="posecraft-snapshot"
              title="Capture the exact camera framing and staged scene currently shown in the viewport."
            >
              {capturingSnapshot ? "Capturing…" : "Snapshot"}
            </button>
            <button type="button" onClick={toggleFullscreen} data-testid="posecraft-toggle-fullscreen" title={fullscreen ? "Exit Fullscreen" : "Fullscreen Viewport"}>
              {fullscreen ? "Exit FS" : "Fullscreen"}
            </button>
          </div>
          <div className="posecraft-viewport-shell">
            <canvas ref={canvasRef} className="posecraft-canvas" data-testid="posecraft-babylon-canvas" />
            <div className="posecraft-overlay">
              <div
                className="posecraft-frame"
                style={{ width: ASPECT_FRAME_WIDTHS[scene.camera.aspect], aspectRatio: String(aspectPreset.ratio), display: capturingClean ? "none" : undefined }}
                data-testid="posecraft-frame-guides"
              >
                {scene.camera.guides.includes("safe") && <div className="posecraft-guide-safe" />}
                {scene.camera.guides.includes("center") && <div className="posecraft-guide-center" />}
                {scene.camera.guides.includes("thirds") && <div className="posecraft-guide-thirds" />}
              </div>
            </div>
            {scene.stage.showLabels && !capturingClean && (
              <div className="posecraft-viewport-labels" data-testid="posecraft-viewport-labels" aria-hidden>
                {viewportLabels.map((entry) => (
                  <span
                    key={entry.id}
                    className={`posecraft-viewport-label ${entry.selected ? "selected" : ""}`}
                    data-testid={`posecraft-viewport-label-${entry.id}`}
                    style={{ left: entry.x, top: entry.y }}
                  >
                    {entry.label}
                  </span>
                ))}
              </div>
            )}
            {showIntro && (
              <div className="posecraft-intro-overlay" data-testid="posecraft-intro-overlay">
                <HelpTip text="PoseCraft blocks people, pose, and camera. Add a figure from the Cast Browser to start." />
                <p className="muted">If the 3D viewport does not appear, your browser may not support WebGL/WebGPU.</p>
              </div>
            )}
            {fullscreen && (
              <div className="posecraft-fullscreen-toolbar" data-testid="posecraft-fullscreen-toolbar">
                <div className="posecraft-gizmo-group" role="group" aria-label="Manipulation mode">
                  <button type="button" className={gizmoMode === "move" ? "primary" : ""} data-testid="posecraft-fs-move"
                    title="Move the whole figure — drag the figure across the stage floor"
                    onClick={() => setGizmoMode("move")}>Move</button>
                  <button type="button" className={gizmoMode === "rotate" ? "primary" : ""} data-testid="posecraft-fs-rotate"
                    title="Rotate the whole figure — turn the entire character (figure yaw). For body-part posing, use Pose body."
                    onClick={() => setGizmoMode("rotate")}>Rotate figure</button>
                  <button type="button" className={gizmoMode === "pose" ? "primary" : ""} data-testid="posecraft-fs-pose"
                    title="Pose body parts — rotate individual joints. To turn the whole character, use Rotate figure."
                    onClick={() => setGizmoMode("pose")}>Pose body</button>
                  <button type="button" data-testid="posecraft-fs-camera"
                    title="Camera — orbit, pan, and zoom the view"
                    onClick={() => setGizmoMode("move")}>Camera</button>
                </div>
                <button
                  type="button"
                  onClick={captureSnapshotNow}
                  disabled={capturingSnapshot}
                  data-testid="posecraft-fs-snapshot"
                  title="Capture the exact camera framing and staged scene currently shown in the viewport."
                >
                  {capturingSnapshot ? "Capturing…" : "Snapshot"}
                </button>
                <button type="button" onClick={toggleFullscreen} data-testid="posecraft-fs-exit">Exit Fullscreen</button>
              </div>
            )}
          </div>
          <div className="posecraft-stage-caption">Neutral floor, grid, axes, soft key light, and lightweight blocking objects only.</div>
        </section>

        {!fullscreen && layout.rightCollapsed && (
          <button type="button" className="posecraft-edge-tab posecraft-edge-tab--right" data-testid="posecraft-expand-right" onClick={expandRight}>◂</button>
        )}
        {!fullscreen && !layout.rightCollapsed && (
          <div className="posecraft-divider" data-testid="posecraft-divider-right"
            onPointerDown={(event) => { draggingDivider.current = "right"; document.body.style.cursor = "col-resize"; event.preventDefault(); }}
            onMouseDown={(event) => { draggingDivider.current = "right"; document.body.style.cursor = "col-resize"; event.preventDefault(); }} />
        )}
        {!fullscreen && !layout.rightCollapsed && (
          <aside
            className="panel posecraft-pane posecraft-pane--right"
            data-testid="posecraft-inspector"
            style={{ width: layout.rightWidth }}
          >
            <div className="posecraft-pane-scroll" data-testid="posecraft-right-scroll">
            <Accordion id="figure" label="Figure" open={rightOpen.has("figure")} onToggle={() => toggleRight("figure")}>
              <PanelHeading title="Inspector" tip="Fine-tune the selected figure or move over to lens and framing." />
              {!selectedFigure ? (
                <p className="empty">Choose a figure from the cast browser.</p>
              ) : (
                <div className="posecraft-inspector-stack">
                  <label className="posecraft-field">
                    <span>Figure Name</span>
                    <input value={selectedFigure.name} data-testid="posecraft-figure-name"
                      onChange={(event) => mutateScene((current) => updateFigure(current, selectedFigure.id, { name: event.target.value }))} />
                  </label>
                  <label className="posecraft-field">
                    <span>Role</span>
                    <select
                      value={selectedFigure.role ?? "unspecified"}
                      data-testid="posecraft-figure-role"
                      onChange={(event) => mutateScene((current) =>
                        setFigureRole(current, selectedFigure.id, event.target.value as FigureRole))}
                    >
                      {FIGURE_ROLES.map((role) => (
                        <option key={role.id} value={role.id}>{role.label}</option>
                      ))}
                    </select>
                  </label>
                  <label className="posecraft-field">
                    <span>Color</span>
                    <select value={selectedFigure.colorId} data-testid="posecraft-figure-color"
                      onChange={(event) => mutateScene((current) => updateFigure(current, selectedFigure.id, { colorId: event.target.value as typeof selectedFigure.colorId }))}>
                      {FIGURE_COLORS.map((color) => (<option key={color.id} value={color.id}>{color.label}</option>))}
                    </select>
                  </label>
                </div>
              )}
            </Accordion>

            <Accordion id="transform" label="Transform" open={rightOpen.has("transform")} onToggle={() => toggleRight("transform")}>
              {!selectedFigure ? (
                <p className="empty">Choose a figure to transform.</p>
              ) : (
                <div className="posecraft-inspector-stack">
              <div className="posecraft-field-grid">
                <label className="posecraft-field"><span>X Position</span>
                  <input type="number" step="0.1" value={selectedFigure.position.x} data-testid="posecraft-figure-x"
                    onChange={(event) => mutateAndFlush((current) => updateFigure(current, selectedFigure.id, { position: { ...selectedFigure.position, x: Number(event.target.value) } }))}
                    onBlur={flushNow} />
                </label>
                <label className="posecraft-field"><span>Z Position</span>
                  <input type="number" step="0.1" value={selectedFigure.position.z} data-testid="posecraft-figure-z"
                    onChange={(event) => mutateAndFlush((current) => updateFigure(current, selectedFigure.id, { position: { ...selectedFigure.position, z: Number(event.target.value) } }))}
                    onBlur={flushNow} />
                </label>
              </div>
              <div className="posecraft-field-grid">
                <label className="posecraft-field"><span>Figure Yaw (whole body)</span>
                  <input type="number" step="1" value={selectedFigure.rotationY} data-testid="posecraft-figure-yaw"
                    title="Turn the entire figure left or right (yaw). This rotates the whole character, not individual body parts."
                    onChange={(event) => mutateAndFlush((current) => updateFigure(current, selectedFigure.id, { rotationY: Number(event.target.value) }))}
                    onBlur={flushNow} />
                </label>
                <label className="posecraft-field"><span>Scale</span>
                  <input type="number" step="0.1" min="0.5" max="1.8" value={selectedFigure.scale} data-testid="posecraft-figure-scale"
                    onChange={(event) => mutateAndFlush((current) => updateFigure(current, selectedFigure.id, { scale: Number(event.target.value) }))}
                    onBlur={flushNow} />
                </label>
              </div>
                </div>
              )}
            </Accordion>

            <Accordion id="pose" label="Pose" open={rightOpen.has("pose")} onToggle={() => toggleRight("pose")}>
              {!selectedFigure ? (
                <p className="empty">Choose a figure to pose.</p>
              ) : selectedFigure.kind === "custom" ? (
                <p className="empty" data-testid="posecraft-custom-no-pose">Custom figures support Move / Rotate / Scale only — skeletal posing is not available for imported meshes this milestone.</p>
              ) : (
                <div className="posecraft-inspector-stack">
              <label className="posecraft-field">
                <span>Joint</span>
                <select value={scene.selectedJoint} data-testid="posecraft-joint-select"
                  onChange={(event) => commitScene(selectJoint(scene, event.target.value as typeof scene.selectedJoint))}>
                  {Object.entries(JOINT_LABELS).map(([joint, label]) => (<option key={joint} value={joint}>{label}</option>))}
                </select>
              </label>
              <div className="posecraft-slider-stack" data-testid="posecraft-joint-sliders">
                {(["x", "y", "z"] as const).map((axis) => (
                  <label className="posecraft-field" key={axis}>
                    <span>{axis.toUpperCase()} Rotation</span>
                    <input type="range" min="-120" max="145" value={selectedJointRotation[axis]} data-testid={`posecraft-joint-${axis}`}
                      onChange={(event) => mutateScene((current) => updateFigureJoint(current, selectedFigure.id, scene.selectedJoint, axis, Number(event.target.value)))} />
                    <strong>{selectedJointRotation[axis]}°</strong>
                  </label>
                ))}
              </div>
              <button type="button" onClick={() => mutateScene((current) => resetFigurePose(current, selectedFigure.id))} data-testid="posecraft-reset-pose">Reset Pose</button>
                </div>
              )}
            </Accordion>

            <Accordion id="pose-intelligence" label="Co-Director Pose Intelligence" open={rightOpen.has("pose-intelligence")} onToggle={() => toggleRight("pose-intelligence")}>
              <PanelHeading title="Pose notes" tip="Co-Director watches balance, support, and contact so later shots can keep the same physical performance. It never changes your pose." />
              <div className="posecraft-pose-intel" data-testid="posecraft-pose-intelligence" data-status={poseIntelStatus}>
                {poseIntelStatus === "idle" && <p className="empty">Pose notes appear after you pose a figure or capture a Snapshot.</p>}
                {poseIntelStatus === "analyzing" && <p className="scene-meta" data-testid="posecraft-pose-intel-loading">Reading the pose…</p>}
                {poseIntelStatus === "unavailable" && (
                  <p className="scene-meta" data-testid="posecraft-pose-intel-unavailable">
                    {poseIntelDetail || "Pose Intelligence is unavailable. Your pose is unchanged."}
                  </p>
                )}
                {(poseIntelStatus === "ready" || poseIntelStatus === "warning" || poseIntelStatus === "degraded") && poseIntel && (
                  <dl className="posecraft-pose-intel-grid" data-testid="posecraft-pose-intel-ready">
                    <div><dt>Balance</dt><dd data-testid="posecraft-pose-intel-balance">{poseIntel.character?.balance || "—"}</dd></div>
                    <div><dt>Primary support</dt><dd data-testid="posecraft-pose-intel-support">{(poseIntel.character?.primarySupport || "—").replace(/_/g, " ")}</dd></div>
                    <div><dt>Character motion</dt><dd data-testid="posecraft-pose-intel-motion">{poseIntel.motion?.rotationDirection || poseIntel.motion?.transitionState || "static"}</dd></div>
                    <div><dt>Contact</dt><dd data-testid="posecraft-pose-intel-contact">{poseIntel.interaction?.handContact?.[0] || poseIntel.interaction?.footContact?.[0] || "none"}</dd></div>
                    <div><dt>Continuity</dt><dd data-testid="posecraft-pose-intel-continuity">Preserve {(poseIntel.constraints?.preserveSupportFoot || "support").replace(/_/g, " ")}</dd></div>
                    <div><dt>Risk</dt><dd data-testid="posecraft-pose-intel-risk">{poseIntel.warnings?.[0] || "none"}</dd></div>
                  </dl>
                )}
                <p className="scene-meta">{poseIntel?.creatorFacingSummary || poseIntelDetail}</p>
                <div className="posecraft-export-actions">
                  <button type="button" className="primary" onClick={() => void runPoseAnalyze()} data-testid="posecraft-analyze-pose">Analyze Pose</button>
                  <button type="button" onClick={() => void runPoseContinuity()} data-testid="posecraft-check-continuity">Check Motion Continuity</button>
                </div>
              </div>
            </Accordion>

            <Accordion id="camera" label="Camera" open={rightOpen.has("camera")} onToggle={() => toggleRight("camera")}>
              <div className="posecraft-lens-row" data-testid="posecraft-lens-row">
            {CAMERA_PRESETS.map((preset) => (
              <button key={preset.lensMm} type="button" className={scene.camera.lensMm === preset.lensMm ? "primary" : ""}
                onClick={() => mutateScene((current) => updateCamera(current, { lensMm: preset.lensMm }))} data-testid={`posecraft-lens-${preset.lensMm}`}>
                {preset.label}
              </button>
            ))}
          </div>
          <div className="posecraft-field-grid">
            <label className="posecraft-field"><span>Aspect</span>
              <select value={scene.camera.aspect} data-testid="posecraft-aspect"
                onChange={(event) => mutateScene((current) => updateCamera(current, { aspect: event.target.value as typeof scene.camera.aspect }))}>
                {CAMERA_ASPECTS.map((aspect) => (<option key={aspect.id} value={aspect.id}>{aspect.label}</option>))}
              </select>
            </label>
            <label className="posecraft-field"><span>Distance</span>
              <input type="number" step="0.1" value={scene.camera.radius} data-testid="posecraft-camera-radius"
                onChange={(event) => mutateScene((current) => updateCamera(current, { radius: Number(event.target.value) }))} />
            </label>
          </div>
          <div className="posecraft-field-grid">
            <label className="posecraft-field"><span>Orbit</span>
              <input type="number" step="0.1" value={scene.camera.alpha} data-testid="posecraft-camera-alpha"
                onChange={(event) => mutateScene((current) => updateCamera(current, { alpha: Number(event.target.value) }))} />
            </label>
            <label className="posecraft-field"><span>Lift</span>
              <input type="number" step="0.1" value={scene.camera.beta} data-testid="posecraft-camera-beta"
                onChange={(event) => mutateScene((current) => updateCamera(current, { beta: Number(event.target.value) }))} />
            </label>
          </div>
          <div className="posecraft-guide-checks" data-testid="posecraft-guide-checks">
            {CAMERA_GUIDES.map((guide) => {
              const active = scene.camera.guides.includes(guide.id);
              return (
                <label key={guide.id} className="posecraft-check">
                  <input type="checkbox" checked={active}
                    onChange={() => mutateScene((current) => updateCamera(current, { guides: active ? current.camera.guides.filter((entry) => entry !== guide.id) : [...current.camera.guides, guide.id] }))} />
                  <span>{guide.label}</span>
                </label>
              );
            })}
          </div>
            </Accordion>

            <Accordion id="export" label="Snapshots + Exports" open={rightOpen.has("export")} onToggle={() => toggleRight("export")}>
              <PanelHeading title="Snapshots + Exports" tip="A Snapshot freezes one exact camera composition for production handoff. Capture a Snapshot, then send it to Co-Director, Image Generation, or Storyboard." />
              <div className="posecraft-snapshot-section" data-testid="posecraft-snapshot-section">
                <div className="posecraft-snapshot-section-head">
                  <span className="posecraft-snapshot-count" data-testid="posecraft-snapshot-count">
                    {snapshotCount} of {POSECRAFT_SNAPSHOT_CAP} Snapshots
                  </span>
                  <button
                    type="button"
                    className="primary posecraft-snapshot-capture"
                    onClick={captureSnapshotNow}
                    disabled={capturingSnapshot}
                    data-testid="posecraft-snapshot-capture"
                    title="Capture the exact camera framing and staged scene currently shown in the viewport."
                  >
                    {capturingSnapshot ? "Capturing…" : "+ Snapshot"}
                  </button>
                </div>
                <div className="posecraft-snapshot-list" data-testid="posecraft-snapshot-list">
                  {(currentDocument.snapshots ?? []).length ? (
                    (currentDocument.snapshots ?? []).map((snap) => {
                      const isSel = currentDocument.selectedSnapshotId === snap.snapshotId;
                      const isRenaming = renamingSnapshotId === snap.snapshotId;
                      const menuOpen = openMenuSnapshotId === snap.snapshotId;
                      const thumbUrl = api.assetUrl(snap.imageAssetId);
                      return (
                        <div
                          key={snap.snapshotId}
                          className={`posecraft-snapshot-card ${isSel ? "selected" : ""}`}
                          data-testid={`posecraft-snapshot-card-${snap.snapshotId}`}
                        >
                          <button
                            type="button"
                            className="posecraft-snapshot-card-main"
                            onClick={() => selectSnapshotForHandoff(snap.snapshotId)}
                            data-testid={`posecraft-snapshot-select-${snap.snapshotId}`}
                            title={isSel ? "Selected for handoff" : "Select this Snapshot for handoff"}
                          >
                            <span className="posecraft-snapshot-thumb" data-testid={`posecraft-snapshot-thumb-${snap.snapshotId}`}>
                              <img src={thumbUrl} alt={snap.name} loading="lazy" />
                            </span>
                            <span className="posecraft-snapshot-meta">
                              {isRenaming ? (
                                <input
                                  autoFocus
                                  value={snapshotRenameValue}
                                  data-testid={`posecraft-snapshot-rename-${snap.snapshotId}`}
                                  onClick={(event) => event.stopPropagation()}
                                  onChange={(event) => setSnapshotRenameValue(event.target.value)}
                                  onKeyDown={(event) => {
                                    if (event.key === "Enter") { event.preventDefault(); commitRenameSnapshot(); }
                                    else if (event.key === "Escape") { event.preventDefault(); cancelRenameSnapshot(); }
                                  }}
                                  onBlur={() => commitRenameSnapshot()}
                                />
                              ) : (
                                <>
                                  <strong>{snap.name}</strong>
                                  <span className="muted">{new Date(snap.createdAt).toLocaleString()}</span>
                                  <span className="muted">Revision {snap.sceneRevision}</span>
                                  <span className="muted">{snap.camera.lensMm}mm · {snap.camera.aspect}</span>
                                </>
                              )}
                            </span>
                            {isSel && (
                              <span className="posecraft-snapshot-selected-badge" data-testid={`posecraft-snapshot-selected-${snap.snapshotId}`} aria-label="Selected for handoff">✓</span>
                            )}
                          </button>
                          <button
                            type="button"
                            className="posecraft-snapshot-card-menu"
                            data-testid={`posecraft-snapshot-menu-${snap.snapshotId}`}
                            aria-label="Snapshot actions"
                            title="Rename, duplicate, delete, preview, restore camera, or export this Snapshot"
                            onClick={(event) => {
                              event.stopPropagation();
                              setOpenMenuSnapshotId(menuOpen ? null : snap.snapshotId);
                            }}
                          >⋯</button>
                          {menuOpen && (
                            <div className="posecraft-figure-menu-popover posecraft-snapshot-menu-popover" data-testid={`posecraft-snapshot-popover-${snap.snapshotId}`}>
                              <button type="button" data-testid={`posecraft-snapshot-rename-btn-${snap.snapshotId}`}
                                onClick={() => startRenameSnapshot(snap.snapshotId, snap.name)}>Rename</button>
                              <button type="button" data-testid={`posecraft-snapshot-duplicate-btn-${snap.snapshotId}`}
                                onClick={() => duplicateSnapshotFromMenu(snap.snapshotId)}>Duplicate</button>
                              <button type="button" data-testid={`posecraft-snapshot-preview-btn-${snap.snapshotId}`}
                                onClick={() => { setPreviewSnapshotId(snap.snapshotId); setOpenMenuSnapshotId(null); }}>Open Preview</button>
                              <button type="button" data-testid={`posecraft-snapshot-restore-cam-btn-${snap.snapshotId}`}
                                onClick={() => restoreSnapshotCamera(snap.snapshotId)}>Restore Camera View</button>
                              <button type="button" data-testid={`posecraft-snapshot-export-img-btn-${snap.snapshotId}`}
                                onClick={() => exportSnapshotImage(snap.snapshotId)}>Export Image</button>
                              <button type="button" className="danger" data-testid={`posecraft-snapshot-delete-btn-${snap.snapshotId}`}
                                onClick={() => deleteSnapshotFromMenu(snap.snapshotId)}>Delete</button>
                            </div>
                          )}
                        </div>
                      );
                    })
                  ) : (
                    <p className="empty" data-testid="posecraft-snapshot-empty">No Snapshots yet. Click + Snapshot to freeze the current camera composition for handoff.</p>
                  )}
                </div>
              </div>
              <div className="posecraft-export-actions" data-testid="posecraft-export-actions">
                <button
                  type="button"
                  className="primary posecraft-send-codirector"
                  onClick={sendToCoDirector}
                  disabled={sendingToCoDirector || !hasSelectedSnapshot}
                  data-testid="posecraft-send-codirector"
                  title={hasSelectedSnapshot ? "Send the selected Snapshot to Co-Director for director notes (composition, eyelines, camera)" : handoffDisabledTip}
                >
                  {sendingToCoDirector ? "Sending…" : "Send to Co-Director"}
                </button>
                <button
                  type="button"
                  className="primary"
                  onClick={sendToImageGeneration}
                  disabled={sendingImageGen || !hasSelectedSnapshot}
                  data-testid="posecraft-send-imagegen"
                  title={hasSelectedSnapshot ? "Send the selected Snapshot to Image Generation" : handoffDisabledTip}
                >
                  {sendingImageGen ? "Sending…" : "Send to Image Generation"}
                </button>
                <button
                  type="button"
                  onClick={sendToStoryboard}
                  disabled={sendingStoryboard || !hasSelectedSnapshot}
                  data-testid="posecraft-send-storyboard"
                  title={hasSelectedSnapshot ? "Send the selected Snapshot to Storyboard" : handoffDisabledTip}
                >
                  {sendingStoryboard ? "Sending…" : "Send to Storyboard"}
                </button>
                <button
                  type="button"
                  onClick={() => void sendToSceneCreator()}
                  disabled={sendingSceneCreator || !hasSelectedSnapshot}
                  data-testid="posecraft-send-scenecreator"
                  title={hasSelectedSnapshot ? "Send the selected Snapshot and pose notes to Scene Creator" : handoffDisabledTip}
                >
                  {sendingSceneCreator ? "Sending…" : "Send to Scene Creator"}
                </button>
                <button
                  type="button"
                  onClick={() => void sendToTimeline()}
                  disabled={sendingTimeline || !hasSelectedSnapshot}
                  data-testid="posecraft-send-timeline"
                  title={hasSelectedSnapshot ? "Send the selected Snapshot and motion notes to Timeline" : handoffDisabledTip}
                >
                  {sendingTimeline ? "Sending…" : "Send to Timeline"}
                </button>
                {!hasSelectedSnapshot && (
                  <p className="scene-meta posecraft-handoff-gate" data-testid="posecraft-handoff-gate">{handoffDisabledTip}</p>
                )}
                {hasSelectedSnapshot && selectedSnapshot && (
                  <p className="scene-meta posecraft-handoff-honesty" data-testid="posecraft-handoff-honesty">
                    PoseCraft Snapshot — Visual Staging Reference · "{selectedSnapshot.name}"
                  </p>
                )}
                <button type="button" onClick={exportStagingReference} data-testid="posecraft-export-reference">
                  Export Staging Reference
                </button>
                <button type="button" onClick={exportSceneJson} data-testid="posecraft-export-scene-json">
                  Export Scene JSON
                </button>
                <p className="scene-meta">Staging reference handoff routes through Image Generation → Library → Storyboard → Timeline.</p>
              </div>
              <div className="posecraft-export-panel" data-testid="posecraft-export-panel" />

              <Accordion id="milestones" label="Advanced — Scene milestones" open={rightOpen.has("milestones")} onToggle={() => toggleRight("milestones")}>
                <PanelHeading title="Scene milestones" tip="Save milestone versions of the live scene. Milestones are scene saves — they are NOT production-handoff Snapshots." />
                <div className="posecraft-field">
                  <label className="posecraft-field">
                    <span>Version Label</span>
                    <input value={versionLabel} placeholder="Wide master before reverse" data-testid="posecraft-version-label"
                      onChange={(event) => setVersionLabel(event.target.value)} />
                  </label>
                  <button type="button" onClick={saveVersionNow} data-testid="posecraft-save-version">Save Version</button>
                </div>
                <div className="posecraft-version-list" data-testid="posecraft-version-list">
                  {currentDocument.savedVersions.length ? (
                    currentDocument.savedVersions.map((version) => {
                      const isRenaming = renamingVersionId === version.id;
                      const menuOpen = openMenuVersionId === version.id;
                      return (
                        <div
                          key={version.id}
                          className="posecraft-version-card"
                          data-testid={`posecraft-version-${version.id}`}
                        >
                          <button
                            type="button"
                            className="posecraft-version-card-main"
                            onClick={() => restoreVersionNow(version.id)}
                            data-testid={`posecraft-version-restore-${version.id}`}
                            title="Restore this milestone"
                          >
                            {isRenaming ? (
                              <input
                                autoFocus
                                value={versionRenameValue}
                                data-testid={`posecraft-version-rename-${version.id}`}
                                onClick={(event) => event.stopPropagation()}
                                onChange={(event) => setVersionRenameValue(event.target.value)}
                                onKeyDown={(event) => {
                                  if (event.key === "Enter") { event.preventDefault(); commitRenameVersion(); }
                                  else if (event.key === "Escape") { event.preventDefault(); cancelRenameVersion(); }
                                }}
                                onBlur={() => commitRenameVersion()}
                              />
                            ) : (
                              <>
                                <strong>{version.label}</strong>
                                <span>Rev {version.revision} · {new Date(version.savedAt).toLocaleString()}</span>
                              </>
                            )}
                          </button>
                          <button
                            type="button"
                            className="posecraft-version-card-menu"
                            data-testid={`posecraft-version-menu-${version.id}`}
                            aria-label="Version actions"
                            title="Rename, duplicate, or delete this milestone"
                            onClick={(event) => {
                              event.stopPropagation();
                              setOpenMenuVersionId(menuOpen ? null : version.id);
                            }}
                          >⋯</button>
                          {menuOpen && (
                            <div className="posecraft-figure-menu-popover posecraft-version-menu-popover" data-testid={`posecraft-version-popover-${version.id}`}>
                              <button type="button" data-testid={`posecraft-version-rename-btn-${version.id}`}
                                onClick={() => startRenameVersion(version.id, version.label)}>Rename</button>
                              <button type="button" data-testid={`posecraft-version-duplicate-btn-${version.id}`}
                                onClick={() => duplicateVersionFromMenu(version.id)}>Duplicate</button>
                              <button type="button" className="danger" data-testid={`posecraft-version-delete-btn-${version.id}`}
                                onClick={() => deleteVersionFromMenu(version.id)}>Delete</button>
                            </div>
                          )}
                        </div>
                      );
                    })
                  ) : (<p className="empty">No saved milestones yet.</p>)}
                </div>
              </Accordion>
            </Accordion>

            {previewSnapshotId && (() => {
              const snap = (currentDocument.snapshots ?? []).find((s) => s.snapshotId === previewSnapshotId);
              if (!snap) return null;
              return (
                <div className="posecraft-snapshot-preview-overlay" data-testid="posecraft-snapshot-preview-overlay" onClick={() => setPreviewSnapshotId(null)}>
                  <div className="posecraft-snapshot-preview-modal" onClick={(event) => event.stopPropagation()}>
                    <div className="posecraft-snapshot-preview-head">
                      <strong>{snap.name}</strong>
                      <span className="muted">Revision {snap.sceneRevision} · {snap.camera.lensMm}mm · {snap.camera.aspect}</span>
                      <button type="button" data-testid="posecraft-snapshot-preview-close" onClick={() => setPreviewSnapshotId(null)}>Close</button>
                    </div>
                    <img src={api.assetUrl(snap.imageAssetId)} alt={snap.name} data-testid={`posecraft-snapshot-preview-img-${snap.snapshotId}`} />
                    <pre className="posecraft-snapshot-preview-summary" data-testid={`posecraft-snapshot-preview-summary-${snap.snapshotId}`}>{snap.semanticSummary}</pre>
                  </div>
                </div>
              );
            })()}
            </div>

            <button type="button" className="posecraft-pane-collapse posecraft-pane-collapse--right" data-testid="posecraft-collapse-right" onClick={collapseRight}>Hide Inspector ▸</button>
          </aside>
        )}
      </section>
    </div>
  );
}
