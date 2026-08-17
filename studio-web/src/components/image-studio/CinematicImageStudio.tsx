/**
 * M4.8 Cinematic Image Studio — artist-first filmmaking workspace.
 * Primary surface polish: references, camera cards, provider browser, continuity, CTA, contact sheet.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api";
import type { Job, Project } from "../../types";
import type { EditorTab } from "../../workspacePrefs";
import { ASPECT_PRESETS } from "../../workspacePrefs";
import { ImageEditWorkspace } from "../imageEdit/ImageEditWorkspace";
import { PromptIntelligencePanel } from "../CoDirector/PromptIntelligencePanel";
import { SpatialReferenceFieldset } from "../spatial-map/SpatialReferenceFieldset";
import { HelpTip } from "../HelpTip";
import type { LibraryAsset } from "../CoDirector/library/assetModel";
import { getAssetName } from "../CoDirector/library/assetModel";
import { CisAccordion } from "./CisAccordion";
import { isReferenceImage, ReferenceBrowser, referenceRole } from "./ReferenceBrowser";
import { ImageProviderBrowser } from "./ImageProviderBrowser";
import { providerSubLabel } from "./providerDisplay";
import { ProductionPipelinePanel } from "./ProductionPipelinePanel";
import type {
  CinematicControls,
  GenerationMode,
  ImageCategory,
  ImageProviderDescriptor,
  ResolutionLabel,
  ShotIntent,
} from "../../contracts/cinematicImageStudio";
import { CREATOR_IMAGE_CATEGORIES, DEFAULT_IMAGE_CATEGORY } from "../../contracts/cinematicImageStudio";
import { DEFAULT_COLOR_GRADE, resolveColorGradeId } from "../../contracts/colorGrades";
import type { ImagePipelineDeploymentPreference } from "../../contracts/imagePipeline";
import type { VisualContinuitySession } from "../../contracts/visualContinuity";
import "./cinematic-image-studio.css";

type StudioMode = "generate" | "edit";

type ResultCard = {
  jobId: string;
  assetId?: string | null;
  providerId?: string;
  family?: string;
  status: string;
  startedAt?: number;
  elapsedSec?: number;
};

const SHOT_INTENTS: { value: ShotIntent; label: string }[] = [
  { value: "establishing", label: "Establishing" },
  { value: "wide", label: "Wide" },
  { value: "medium", label: "Medium" },
  { value: "close_up", label: "Close-up" },
  { value: "extreme_close_up", label: "Extreme CU" },
  { value: "over_shoulder", label: "Over shoulder" },
  { value: "pov", label: "POV" },
  { value: "two_shot", label: "Two-shot" },
  { value: "insert", label: "Insert" },
  { value: "custom", label: "Custom" },
];

const CATEGORIES = CREATOR_IMAGE_CATEGORIES;

const LENS_OPTIONS: { value: string; tip: string }[] = [
  {
    value: "24mm",
    tip: "Best for wide environments, establishing shots, and exaggerated perspective.",
  },
  {
    value: "35mm",
    tip: "Natural cinematic perspective. Excellent general filmmaking lens.",
  },
  {
    value: "50mm",
    tip: "Natural human perspective. Ideal for dialogue scenes.",
  },
  {
    value: "85mm",
    tip: "Portrait lens with beautiful facial compression.",
  },
  {
    value: "135mm",
    tip: "Long dramatic compression for emotional closeups.",
  },
  {
    value: "Anamorphic 40mm",
    tip: "Widescreen cinematic feel with characteristic anamorphic compression.",
  },
  {
    value: "Zoom 24–70",
    tip: "Flexible coverage from environment wides through medium portraits.",
  },
];

const LIGHTING_OPTIONS = [
  "Natural soft daylight",
  "Motivated practicals",
  "Hard key / noir",
  "Overcast ambient",
  "Neon night",
  "Golden hour rim",
];

function projectDefaults(project: Project): Record<string, unknown> {
  try {
    return project.defaults_json ? JSON.parse(project.defaults_json) : {};
  } catch {
    return {};
  }
}

function continuityGrade(session: VisualContinuitySession | null): string {
  if (!session) return "Not loaded";
  const approved = session.approvedImageIds?.length || 0;
  const refs = session.referenceAssetIds?.length || 0;
  if (approved >= 4 || refs >= 6) return "Excellent";
  if (approved >= 1 || refs >= 2) return "Good";
  return "Building";
}

function estimateCostLabel(targets: ImageProviderDescriptor[]): string {
  const hosted = targets.filter((t) => t.requiresPaidConfirmation);
  if (!hosted.length) return "Local GPU";
  // Honest estimate band — not a live quote.
  const low = Math.max(0.04, hosted.length * 0.04);
  const high = hosted.length * 0.18;
  return `~$${low.toFixed(2)}–$${high.toFixed(2)}`;
}

function estimateTimeLabel(targets: ImageProviderDescriptor[], batchSize: number): string {
  if (!targets.length) return "—";
  const localHeavy = targets.every((t) => t.source !== "hosted");
  const base = localHeavy ? 18 : 12;
  const seconds = Math.max(8, base * Math.max(1, batchSize) * Math.min(targets.length, 4));
  return `${seconds} sec`;
}

function effectivePrompt(prompt: string, controls: CinematicControls): string {
  if (controls.shotIntent !== "custom") return prompt;
  const custom = (controls.customShotIntent || "").trim();
  if (!custom) return prompt;
  return `${prompt.trim()}\n\nCustom shot intent: ${custom}`.trim();
}

function tagFromFilename(name: string): string {
  const stem = name.replace(/\.[^.]+$/, "").replace(/[^\w\s-]+/g, " ").trim();
  return stem.slice(0, 80) || "library_upload";
}

function providerSupportsReferences(provider: ImageProviderDescriptor | null | undefined): boolean | null {
  const caps = provider?.metadata?.capabilities;
  if (!caps || typeof caps !== "object" || !("supportsReferences" in caps)) return null;
  return Boolean((caps as { supportsReferences?: unknown }).supportsReferences);
}

export function CinematicImageStudio({
  project,
  onChange,
  onGo,
}: {
  project: Project;
  onChange: () => Promise<void>;
  onGo: (tab: EditorTab) => void;
}) {
  const d = projectDefaults(project);
  const [studioMode, setStudioMode] = useState<StudioMode>("generate");
  const [prompt, setPrompt] = useState("");
  const [negative, setNegative] = useState(project.negative_prompt || "");
  const [controls, setControls] = useState<CinematicControls>({
    aspectRatio: String(d.aspect || "16:9"),
    shotIntent: "medium",
    category: DEFAULT_IMAGE_CATEGORY,
    lens: "35mm",
    lighting: "Natural soft daylight",
    colorTreatment: "Neutral cinematic",
    colorGradePreset: DEFAULT_COLOR_GRADE,
    customShotIntent: "",
  });
  const [resolution, setResolution] = useState<ResolutionLabel>("1K");
  const [batchSize, setBatchSize] = useState(1);
  const [mode, setMode] = useState<GenerationMode>("best_match");
  const [chosenProviderId, setChosenProviderId] = useState<string>("");
  const [selectedProviderIds, setSelectedProviderIds] = useState<string[]>([]);
  const [providers, setProviders] = useState<ImageProviderDescriptor[]>([]);
  const [allProviders, setAllProviders] = useState<ImageProviderDescriptor[]>([]);
  const [bestMatch, setBestMatch] = useState<ImageProviderDescriptor | null>(null);
  const [paidConfirmIds, setPaidConfirmIds] = useState<string[]>([]);
  const [hostedChoice, setHostedChoice] = useState<"local_only" | "allow_hosted">("local_only");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [seed, setSeed] = useState(project.seed ?? -1);
  const [guidance, setGuidance] = useState<number | "">("");
  const [steps, setSteps] = useState<number | "">("");
  const [refIds, setRefIds] = useState<string[]>([]);
  const [pendingIds, setPendingIds] = useState<string[]>([]);
  const [libraryItems, setLibraryItems] = useState<LibraryAsset[]>([]);
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [piStatus, setPiStatus] = useState("Co-Director");
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const [sceneId, setSceneId] = useState("");
  const [continuityOn, setContinuityOn] = useState(false);
  const [continuitySession, setContinuitySession] = useState<VisualContinuitySession | null>(null);
  const [spatialMapId, setSpatialMapId] = useState<string | undefined>();
  const [spatialMapVersion, setSpatialMapVersion] = useState<string | undefined>();
  const [spatialCameraId, setSpatialCameraId] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [results, setResults] = useState<ResultCard[]>([]);
  const [undoPanelId, setUndoPanelId] = useState<string | null>(null);
  const [replacePanelId, setReplacePanelId] = useState<string | null>(null);

  const loadLibrary = useCallback(async () => {
    try {
      const res = await api.library(project.id);
      const items = (res.items || []).filter((item: LibraryAsset) => isReferenceImage(item));
      setLibraryItems(items);
    } catch {
      setLibraryItems([]);
    }
  }, [project.id]);

  useEffect(() => {
    void loadLibrary();
  }, [loadLibrary, project.assets]);

  const scenes = useMemo(
    () => [...(project.scenes || [])].sort((a, b) => (a.index ?? 0) - (b.index ?? 0)),
    [project.scenes]
  );
  const selectedScene = scenes.find((s) => s.id === sceneId) || null;

  const refreshProviders = useCallback(async () => {
    try {
      const [modeRes, allRes] = await Promise.all([
        api.imageStudio.providersForMode({
          mode,
          prompt,
          purpose: controls.category,
          preferredFamily: chosenProviderId
            ? providers.find((p) => p.id === chosenProviderId)?.family
            : undefined,
        }),
        api.imageStudio.listProviders(true),
      ]);
      const modeProviders = modeRes.providers || [];
      const catalog = allRes.providers || modeProviders;
      setProviders(modeProviders);
      setAllProviders(catalog);
      setBestMatch(modeRes.bestMatch || null);
      setPaidConfirmIds(modeRes.paidProvidersRequireConfirmation || []);
      if (mode === "all_models") {
        setSelectedProviderIds((prev) => {
          if (prev.length) {
            const valid = new Set(catalog.map((p) => p.id));
            const kept = prev.filter((id) => valid.has(id));
            if (kept.length) return kept;
          }
          return catalog.filter((p) => p.readiness === "ready").map((p) => p.id);
        });
      }
    } catch {
      try {
        const all = await api.imageStudio.listProviders(true);
        setProviders(all.providers || []);
        setAllProviders(all.providers || []);
      } catch {
        setProviders([]);
        setAllProviders([]);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, prompt, controls.category, chosenProviderId]);

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("adept_cis_seed");
      if (raw) {
        const seedPayload = JSON.parse(raw) as {
          prompt?: string;
          panelId?: string;
          continuitySessionId?: string;
          assetId?: string;
        };
        if (seedPayload.prompt) setPrompt(seedPayload.prompt);
        if (seedPayload.panelId) setReplacePanelId(seedPayload.panelId);
        if (seedPayload.assetId) {
          void api.imageStudio
            .reopenAsset(project.id, seedPayload.assetId)
            .then((res) => {
              const r = res.reopen;
              if (r.prompt) setPrompt(r.prompt);
              if (r.negativePrompt != null) setNegative(r.negativePrompt);
              if (r.referenceAssetIds?.length) setRefIds(r.referenceAssetIds);
              if (r.sceneId) setSceneId(String(r.sceneId));
              setSpatialMapId(r.spatialMapId ? String(r.spatialMapId) : undefined);
              setSpatialMapVersion(r.spatialMapVersion ? String(r.spatialMapVersion) : undefined);
              setSpatialCameraId(r.spatialCameraId ? String(r.spatialCameraId) : undefined);
              if (r.controls) {
                setControls((c) => ({
                  ...c,
                  ...(r.controls as Partial<CinematicControls>),
                  aspectRatio: String(r.controls.aspectRatio || c.aspectRatio),
                  shotIntent: (r.controls.shotIntent as ShotIntent) || c.shotIntent,
                  category: (r.controls.category as ImageCategory) || c.category,
                  colorGradePreset: resolveColorGradeId(
                    String(r.controls.colorGradePreset || r.controls.colorTreatment || c.colorGradePreset || "")
                  ),
                }));
              }
            })
            .catch(() => undefined);
        }
        if (seedPayload.continuitySessionId) {
          void api.imageStudio
            .getContinuitySession(project.id, seedPayload.continuitySessionId)
            .then((r) => {
              setContinuitySession(r.session);
              setContinuityOn(true);
            })
            .catch(() => undefined);
        }
        sessionStorage.removeItem("adept_cis_seed");
      }
    } catch {
      /* ignore */
    }
  }, [project.id]);

  useEffect(() => {
    const t = setTimeout(() => void refreshProviders(), 300);
    return () => clearTimeout(t);
  }, [refreshProviders]);

  useEffect(() => {
    const active = jobs.filter((j) => !["done", "failed", "cancelled"].includes(j.status));
    if (!active.length) return;
    const tick = setInterval(() => {
      Promise.all(active.map((j) => api.getJob(j.id)))
        .then((updated) => {
          setJobs((prev) => {
            const map = new Map(updated.map((j) => [j.id, j]));
            return prev.map((j) => map.get(j.id) || j);
          });
          const cards: ResultCard[] = [];
          for (const j of updated) {
            let assetId: string | undefined;
            let family: string | undefined;
            try {
              const p = JSON.parse(j.params_json || "{}");
              assetId = p.output_asset_id || p.outputAssetId;
              family = p.imageIntent?.enginePreference || p.recommendation?.executionFamily;
            } catch {
              /* ignore */
            }
            cards.push({
              jobId: j.id,
              assetId,
              family,
              status: j.status,
            });
          }
          setResults((prev) => {
            const map = new Map(prev.map((c) => [c.jobId, c]));
            for (const c of cards) {
              const prior = map.get(c.jobId);
              const startedAt = prior?.startedAt || Date.now();
              const elapsedSec =
                c.status === "done" || c.status === "failed"
                  ? Math.max(1, Math.round((Date.now() - startedAt) / 1000))
                  : prior?.elapsedSec;
              map.set(c.jobId, { ...prior, ...c, startedAt, elapsedSec });
            }
            return Array.from(map.values());
          });
          if (updated.some((j) => j.status === "done")) void onChange();
        })
        .catch(() => undefined);
    }, 1500);
    return () => clearInterval(tick);
  }, [jobs, onChange]);

  const inheritContinuity = async (nextSceneId?: string) => {
    const id = (nextSceneId || sceneId).trim();
    if (!id) {
      setMsg("Choose a scene to load continuity.");
      return;
    }
    try {
      const res = await api.imageStudio.inheritContinuityFromScene(project.id, id);
      setSceneId(id);
      setContinuitySession(res.session);
      setContinuityOn(true);
      if (res.session.referenceAssetIds?.length) {
        setRefIds((prev) => Array.from(new Set([...prev, ...res.session.referenceAssetIds])));
      }
      if (res.session.lensLanguage) {
        setControls((c) => ({ ...c, lens: res.session.lensLanguage || c.lens }));
      }
      if (res.session.lightingDirection) {
        setControls((c) => ({ ...c, lighting: res.session.lightingDirection || c.lighting }));
      }
      if (res.session.colorTreatment) {
        const grade = resolveColorGradeId(res.session.colorTreatment);
        setControls((c) => ({
          ...c,
          colorTreatment: res.session.colorTreatment || c.colorTreatment,
          colorGradePreset: grade,
        }));
      }
      if (res.session.aspectRatio) {
        setControls((c) => ({ ...c, aspectRatio: res.session.aspectRatio || c.aspectRatio }));
      }
      setMsg("Scene continuity loaded.");
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  };

  const resolveTargets = (): ImageProviderDescriptor[] => {
    if (mode === "all_models") {
      const catalog = allProviders.length ? allProviders : providers;
      let selected = catalog.filter((p) => selectedProviderIds.includes(p.id) && p.readiness === "ready");
      if (hostedChoice === "local_only") {
        selected = selected.filter((p) => !p.requiresPaidConfirmation);
      }
      return selected;
    }
    if (mode === "choose_model") {
      const chosen = providers.find((p) => p.id === chosenProviderId);
      return chosen ? [chosen] : [];
    }
    return bestMatch ? [bestMatch] : providers[0] ? [providers[0]] : [];
  };

  const generate = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const targets = resolveTargets();
      if (!targets.length) {
        setMsg(
          mode === "all_models"
            ? "Select at least one ready model in the Provider Browser."
            : "No ready image provider for this mode. Check Production Dock."
        );
        return;
      }

      const needsPaid = targets.some((t) => t.requiresPaidConfirmation);
      if (needsPaid && hostedChoice !== "allow_hosted") {
        setMsg("Allow hosted API models in the confirmation card before generating.");
        return;
      }

      const queued: Job[] = [];
      const cards: ResultCard[] = [];
      const failures: string[] = [];
      const promptForGen = effectivePrompt(prompt, controls);

      for (const target of targets) {
        try {
          const preview = await api.imageStudio.compilePreview(project.id, {
            prompt: promptForGen,
            negativePrompt: negative,
            projectId: project.id,
            mode,
            modelFamilyPreference: target.family,
            providerId: target.providerPreference,
            modelId: target.modelId || target.id,
            batchSize: mode === "all_models" ? 1 : batchSize,
            resolution,
            controls,
            referenceAssetIds: refIds,
            sceneId: sceneId || undefined,
            continuitySessionId: continuityOn ? continuitySession?.id : undefined,
            inheritContinuityFromScene: continuityOn && !continuitySession?.id && !!sceneId,
            spatialMapId,
            spatialMapVersion,
            spatialCameraId,
            purpose: controls.category,
            panelId: replacePanelId || undefined,
            runPromptIntelligence: true,
            advanced:
              advancedOpen && (seed >= 0 || guidance !== "" || steps !== "")
                ? {
                    seed: seed >= 0 ? seed : undefined,
                    guidance: guidance === "" ? undefined : Number(guidance),
                    steps: steps === "" ? undefined : Number(steps),
                  }
                : undefined,
          });

          const body = {
            ...(preview.imageProductBody || {}),
            lockModelFamily: true,
          };
          if (preview.continuitySessionId && !continuitySession) {
            try {
              const s = await api.imageStudio.getContinuitySession(
                project.id,
                preview.continuitySessionId
              );
              setContinuitySession(s.session);
              setContinuityOn(true);
            } catch {
              /* ignore */
            }
          }

          const result = await api.imageProduct.generate(project.id, body);
          const ids = (result.jobs || []).map((j) => j.jobId).filter(Boolean) as string[];
          const primary = result.jobId || ids[0];
          const fetched = await Promise.all(ids.map((id) => api.getJob(id)));
          const list = fetched.length ? fetched : primary ? [await api.getJob(primary)] : [];
          for (const j of list) {
            queued.push(j);
            cards.push({
              jobId: j.id,
              providerId: target.id,
              family: target.family,
              status: j.status,
              startedAt: Date.now(),
            });
          }
        } catch (err: unknown) {
          const reason = err instanceof Error ? err.message : String(err);
          failures.push(`${target.displayName}: ${reason}`);
          cards.push({
            jobId: `failed-${target.id}-${Date.now()}`,
            providerId: target.id,
            family: target.family,
            status: "failed",
          });
        }
      }

      setJobs((prev) => [...queued, ...prev].slice(0, 24));
      setResults((prev) => [...cards, ...prev].slice(0, 48));
      if (failures.length && queued.length) {
        setMsg(`Partial batch: ${failures.length} provider(s) failed; others continued. ${failures[0]}`);
      } else if (failures.length && !queued.length) {
        setMsg(failures.join(" · "));
      }
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const reopenFromAsset = async (assetId: string) => {
    try {
      const res = await api.imageStudio.reopenAsset(project.id, assetId);
      const r = res.reopen;
      if (r.prompt) setPrompt(r.prompt);
      if (r.negativePrompt != null) setNegative(r.negativePrompt);
      if (r.referenceAssetIds?.length) setRefIds(r.referenceAssetIds);
      if (r.sceneId) setSceneId(String(r.sceneId));
      if (r.panelId) setReplacePanelId(String(r.panelId));
      setSpatialMapId(r.spatialMapId ? String(r.spatialMapId) : undefined);
      setSpatialMapVersion(r.spatialMapVersion ? String(r.spatialMapVersion) : undefined);
      setSpatialCameraId(r.spatialCameraId ? String(r.spatialCameraId) : undefined);
      if (r.controls) {
        setControls((c) => ({
          ...c,
          ...(r.controls as Partial<CinematicControls>),
          aspectRatio: String(r.controls.aspectRatio || c.aspectRatio),
          shotIntent: (r.controls.shotIntent as ShotIntent) || c.shotIntent,
          category: (r.controls.category as ImageCategory) || c.category,
          colorGradePreset: resolveColorGradeId(
            String(r.controls.colorGradePreset || r.controls.colorTreatment || c.colorGradePreset || "")
          ),
        }));
      }
      if (r.continuitySessionId) {
        const s = await api.imageStudio.getContinuitySession(project.id, r.continuitySessionId);
        setContinuitySession(s.session);
        setContinuityOn(true);
      }
      setMsg("Restored shot setup from source image.");
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  };

  const approveImage = async (assetId: string) => {
    if (!continuitySession?.id) {
      setMsg("Load scene continuity before approving into the session.");
      return;
    }
    try {
      const res = await api.imageStudio.approveContinuityImage(
        project.id,
        continuitySession.id,
        assetId
      );
      setContinuitySession(res.session);
      setMsg("Image approved into continuity session.");
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  };

  const addToStoryboard = async (assetId: string) => {
    try {
      if (replacePanelId) {
        const res = await api.storyboardStudio.replacePanel(project.id, {
          panelId: replacePanelId,
          assetId,
          prompt,
          label: controls.shotIntent,
          lens: controls.lens || "",
          shotSize: controls.shotIntent,
          continuitySessionId: continuitySession?.id,
          spatialMapId,
          spatialMapVersion,
          sceneId: sceneId || undefined,
          scriptwriterSceneId: sceneId || undefined,
        });
        setUndoPanelId(res.panelId);
        setMsg("Storyboard panel replaced.");
        return;
      }
      const res = await api.storyboardStudio.addImage(project.id, {
        assetId,
        prompt,
        label: controls.shotIntent,
        lens: controls.lens || "",
        shotSize: controls.shotIntent,
        continuitySessionId: continuitySession?.id,
        spatialMapId,
        spatialMapVersion,
        sceneId: sceneId || undefined,
        scriptwriterSceneId: sceneId || undefined,
      });
      setUndoPanelId(res.panelId);
      setMsg(`Added to Storyboard · page ${res.slot.pageIndex + 1}, slot ${res.slot.slotIndex + 1}`);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  };

  const undoStoryboardAdd = async () => {
    if (!undoPanelId) return;
    try {
      await api.storyboardStudio.undoAddImage(project.id, undoPanelId);
      setMsg("Storyboard add undone.");
      setUndoPanelId(null);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  };

  const uploadToLibrary = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true);
    setMsg(null);
    try {
      const asset = await api.uploadAsset(project.id, file, tagFromFilename(file.name), "image");
      await onChange();
      await loadLibrary();
      setHighlightId(asset.id);
      setMsg("Image added to the project Library. Select it, then click Add Reference.");
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Could not upload that image to the Library.");
    } finally {
      setUploading(false);
      if (uploadInputRef.current) uploadInputRef.current.value = "";
    }
  };

  const addReferences = () => {
    if (!pendingIds.length) return;
    const next = Array.from(new Set([...refIds, ...pendingIds]));
    setRefIds(next);
    setPendingIds([]);
  };

  const groupedResults = useMemo(() => {
    const groups = new Map<string, ResultCard[]>();
    for (const r of results) {
      const key = r.family || r.providerId || "result";
      const list = groups.get(key) || [];
      list.push(r);
      groups.set(key, list);
    }
    return Array.from(groups.entries());
  }, [results]);

  const generateTargets = resolveTargets();
  const paidOk = hostedChoice === "allow_hosted";
  const accordionKey = `adept_cis_accordion_${project.id}`;
  const supportsRefs = providerSupportsReferences(generateTargets[0] || bestMatch);
  const activeAssets: LibraryAsset[] = refIds.map((id) => {
    const found = libraryItems.find((item) => item.id === id);
    return found || { id, tag: id.slice(0, 8), kind: "image" };
  });
  const showHostedCard =
    mode === "all_models" ||
    paidConfirmIds.length > 0 ||
    generateTargets.some((t) => t.requiresPaidConfirmation);
  const pipelineDeploymentPreference: ImagePipelineDeploymentPreference =
    hostedChoice === "local_only"
      ? "local"
      : mode === "choose_model"
        ? (providers.find((provider) => provider.id === chosenProviderId)?.source === "hosted" ? "api" : "local")
        : "best-match";

  if (studioMode === "edit") {
    return (
      <div className="page cinematic-image-studio">
        <div className="cis-mode-tabs">
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
    <div className="page cinematic-image-studio" data-testid="cinematic-image-studio">
      <div className="cis-mode-tabs">
        <button type="button" className="primary" onClick={() => setStudioMode("generate")}>
          Generate
        </button>
        <button type="button" onClick={() => setStudioMode("edit")}>
          Edit
        </button>
        <button type="button" className="ghost" onClick={() => onGo("script")}>
          Open Storyboard
        </button>
      </div>

      <header className="cis-header">
        <h1>Cinematic Image Generator</h1>
        <p className="muted">
          Craft production frames for storyboard sequences — describe the shot, set references, and generate.
        </p>
      </header>

      {msg && <p className="pill warn">{msg}</p>}

      <div className="cis-stack">
        {/* 1. Prompt */}
        <section className="cis-card cis-card--prompt">
          <h2 className="cis-card__title">Prompt</h2>
          <div className="field">
            <label htmlFor="cis-prompt">Shot description</label>
            <textarea
              id="cis-prompt"
              rows={5}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe the shot as a filmmaker — subject, action, atmosphere…"
            />
          </div>
          <div className="cis-row" style={{ marginTop: "0.75rem" }}>
            <div className="field">
              <label>Category</label>
              <select
                data-testid="cis-category"
                value={controls.category}
                onChange={(e) =>
                  setControls((c) => ({ ...c, category: e.target.value as ImageCategory }))
                }
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Mode</label>
              <select value={mode} onChange={(e) => setMode(e.target.value as GenerationMode)}>
                <option value="best_match">Best Match</option>
                <option value="choose_model">Choose Model</option>
                <option value="all_models">All Image Models</option>
              </select>
            </div>
            <div className="field">
              <label>Batch</label>
              <select
                value={batchSize}
                onChange={(e) => setBatchSize(Number(e.target.value))}
                disabled={mode === "all_models"}
              >
                {[1, 2, 3, 4].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {mode === "best_match" && bestMatch && (
            <p className="muted tiny" style={{ marginTop: "0.65rem" }}>
              Using <strong>{bestMatch.displayName}</strong> · {bestMatch.costHint || "Local"}
            </p>
          )}
          {mode === "choose_model" && (
            <div className="field" style={{ marginTop: "0.65rem" }}>
              <label>Model</label>
              <select value={chosenProviderId} onChange={(e) => setChosenProviderId(e.target.value)}>
                <option value="">Select a model…</option>
                {providers.map((p) => {
                  const sub = providerSubLabel(p);
                  return (
                    <option key={p.id} value={p.id} disabled={p.readiness !== "ready"}>
                      {p.displayName}
                      {sub ? ` · ${sub}` : ""} · {p.source === "hosted" ? "API" : "Local"} · {p.readiness}
                    </option>
                  );
                })}
              </select>
            </div>
          )}
        </section>

        <CisAccordion id="image-plan" title="Image Plan" defaultOpen persistKey={accordionKey}>
          <ProductionPipelinePanel
            projectId={project.id}
            prompt={effectivePrompt(prompt, controls)}
            purpose={controls.category}
            referenceAssetIds={refIds}
            deploymentPreference={pipelineDeploymentPreference}
            allowApiDeployment={paidOk}
            spatialMapId={spatialMapId}
            spatialMapVersion={spatialMapVersion}
            colorGradePreset={resolveColorGradeId(controls.colorGradePreset || controls.colorTreatment)}
            onColorGradeChange={(id) =>
              setControls((c) => ({ ...c, colorGradePreset: id, colorTreatment: id }))
            }
            hideTitle
          />
        </CisAccordion>

        <CisAccordion
          id="references"
          title="References"
          defaultOpen
          persistKey={accordionKey}
          status={refIds.length ? `${refIds.length} active` : undefined}
          headerAction={
            <>
              <input
                ref={uploadInputRef}
                type="file"
                accept="image/*"
                hidden
                data-testid="cis-upload-library-input"
                onChange={(event) => void uploadToLibrary(event.target.files?.[0])}
              />
              <button
                type="button"
                className="ghost"
                disabled={uploading}
                data-testid="cis-upload-library"
                onClick={() => uploadInputRef.current?.click()}
              >
                {uploading ? "Uploading…" : "Upload Image to Library"}
              </button>
            </>
          }
        >
          <ReferenceBrowser
            assets={libraryItems}
            pendingIds={pendingIds}
            activeIds={refIds}
            highlightId={highlightId}
            onPendingChange={setPendingIds}
          />
          <div className="cis-ref-bind">
            <button
              type="button"
              className="primary"
              disabled={!pendingIds.length}
              data-testid="cis-add-reference"
              onClick={addReferences}
            >
              Add Reference
            </button>
            {pendingIds.length ? (
              <span className="muted tiny">{pendingIds.length} selected</span>
            ) : null}
          </div>
          <div className="cis-active-refs" data-testid="cis-active-references">
            <div className="cis-active-refs__header">
              <h3>Active References</h3>
              <span className="muted tiny" data-testid="cis-active-ref-count">
                {refIds.length} active reference{refIds.length === 1 ? "" : "s"}
              </span>
            </div>
            {!activeAssets.length ? (
              <p className="muted tiny">Select images in the Library, then click Add Reference.</p>
            ) : (
              <ul className="cis-active-ref-list">
                {activeAssets.map((asset) => {
                  const role = referenceRole(asset);
                  const supported = supportsRefs;
                  return (
                    <li key={asset.id} className="cis-active-ref-chip" data-testid={`cis-active-ref-${asset.id}`}>
                      <img src={api.assetUrl(asset.id)} alt="" />
                      <span className="cis-active-ref-chip__meta">
                        <strong>{getAssetName(asset)}</strong>
                        <span>
                          {role}
                          {supported === true ? " ✓" : supported === false ? " ⚠" : ""}
                        </span>
                        {supported === false ? (
                          <span className="cis-active-ref-chip__warn">
                            Selected generator cannot directly use this reference.
                          </span>
                        ) : null}
                      </span>
                      <button
                        type="button"
                        className="ghost"
                        aria-label={`Remove ${getAssetName(asset)}`}
                        data-testid={`cis-remove-ref-${asset.id}`}
                        onClick={() => setRefIds((prev) => prev.filter((id) => id !== asset.id))}
                      >
                        ×
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </CisAccordion>

        <CisAccordion
          id="camera"
          title="Camera"
          defaultOpen
          persistKey={accordionKey}
          status={`${controls.shotIntent.replace(/_/g, " ")} · ${controls.lens} · ${controls.aspectRatio}`}
        >
          <div className="cis-row">
            <div className="field">
              <label>Shot Intent</label>
              <select
                value={controls.shotIntent}
                onChange={(e) =>
                  setControls((c) => ({ ...c, shotIntent: e.target.value as ShotIntent }))
                }
              >
                {SHOT_INTENTS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <span className="cis-field-label">
                <label>Lens</label>
              </span>
              <div className="cis-lens-grid" role="group" aria-label="Lens presets">
                {LENS_OPTIONS.map((l) => (
                  <div key={l.value} className="cis-lens-option">
                    <button
                      type="button"
                      className={controls.lens === l.value ? "primary" : "ghost"}
                      aria-pressed={controls.lens === l.value}
                      onClick={() => setControls((c) => ({ ...c, lens: l.value }))}
                    >
                      {l.value}
                    </button>
                    <HelpTip label={`What is ${l.value}?`} content={l.tip} />
                  </div>
                ))}
              </div>
            </div>
            <div className="field">
              <label>Ratio</label>
              <select
                value={controls.aspectRatio}
                onChange={(e) => setControls((c) => ({ ...c, aspectRatio: e.target.value }))}
              >
                {ASPECT_PRESETS.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Resolution</label>
              <select
                value={resolution}
                onChange={(e) => setResolution(e.target.value as ResolutionLabel)}
              >
                <option value="1K">1K</option>
                <option value="2K">2K</option>
                <option value="4K">4K</option>
                <option value="8K">8K</option>
              </select>
            </div>
          </div>
          {controls.shotIntent === "custom" && (
            <div className="field cis-custom-intent" data-testid="cis-custom-shot-intent">
              <label htmlFor="cis-custom-intent">Describe custom shot intent</label>
              <textarea
                id="cis-custom-intent"
                value={controls.customShotIntent || ""}
                onChange={(e) => setControls((c) => ({ ...c, customShotIntent: e.target.value }))}
                placeholder="e.g. Low dutch angle through smoke, hero framed off-center…"
              />
            </div>
          )}
        </CisAccordion>

        <CisAccordion
          id="lighting"
          title="Lighting"
          persistKey={accordionKey}
          status={controls.lighting || undefined}
        >
          <div className="cis-row">
            <div className="field">
              <label>Lighting</label>
              <select
                value={controls.lighting || ""}
                onChange={(e) => setControls((c) => ({ ...c, lighting: e.target.value }))}
              >
                {LIGHTING_OPTIONS.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </CisAccordion>

        {mode === "all_models" && (
          <CisAccordion id="all-models" title="All Image Models" persistKey={accordionKey}>
            <ImageProviderBrowser
              providers={allProviders.length ? allProviders : providers}
              selectedIds={selectedProviderIds}
              bestMatchId={bestMatch?.id}
              onChange={setSelectedProviderIds}
            />
          </CisAccordion>
        )}

        {showHostedCard && (
          <CisAccordion
            id="hosted-api"
            title="Hosted API Usage"
            persistKey={accordionKey}
            status={hostedChoice === "allow_hosted" ? "Hosted allowed" : "Local only"}
            className="cis-hosted-card"
          >
            <div className="cis-hosted-card__body" data-testid="cis-hosted-api-card">
              <fieldset className="cis-hosted-card__options" role="radiogroup" aria-label="Generation Source">
                <legend>Generation Source</legend>
                <label>
                  <input
                    type="radio"
                    name="cis-hosted"
                    checked={hostedChoice === "local_only"}
                    onChange={() => setHostedChoice("local_only")}
                  />
                  <span>Local Models Only</span>
                </label>
                <label>
                  <input
                    type="radio"
                    name="cis-hosted"
                    checked={hostedChoice === "allow_hosted"}
                    onChange={() => setHostedChoice("allow_hosted")}
                  />
                  <span>Allow Hosted API Models</span>
                </label>
              </fieldset>
              <div className={`cis-hosted-card__cost${paidOk ? "" : " is-muted"}`}>
                Estimated hosted cost: <strong>{paidOk ? estimateCostLabel(generateTargets) : "$0.00"}</strong>
                <div className="tiny muted">Hosted cost applies only when hosted models are used.</div>
              </div>
            </div>
          </CisAccordion>
        )}

        <CisAccordion
          id="continuity"
          title="Continuity"
          persistKey={accordionKey}
          status={selectedScene?.name || "No scene"}
        >
          <div className="cis-continuity-grid">
            <div className="cis-continuity-stat">
              <span>Current Scene</span>
              <strong>{selectedScene?.name || "None selected"}</strong>
            </div>
            <div className="cis-continuity-stat">
              <span>Previous Images</span>
              <strong>
                {(continuitySession?.approvedImageIds?.length || 0) +
                  (continuitySession?.referenceAssetIds?.length || 0)}
              </strong>
            </div>
            <div className="cis-continuity-stat">
              <span>Consistency</span>
              <strong>{continuityGrade(continuitySession)}</strong>
            </div>
          </div>
          <div className="cis-continuity-actions">
            <div className="field" style={{ minWidth: "220px", flex: 1 }}>
              <label htmlFor="cis-scene">Scene</label>
              <select
                id="cis-scene"
                value={sceneId}
                onChange={(e) => {
                  const next = e.target.value;
                  setSceneId(next);
                  if (next) void inheritContinuity(next);
                }}
                data-testid="cis-scene-select"
              >
                <option value="">Select a scene…</option>
                {scenes.map((scene) => (
                  <option key={scene.id} value={scene.id}>
                    {scene.name || `Scene ${scene.index + 1}`}
                  </option>
                ))}
              </select>
            </div>
            <button type="button" onClick={() => void inheritContinuity()} disabled={!sceneId}>
              Load Scene References
            </button>
            <label className="tiny" style={{ display: "inline-flex", gap: "0.4rem", alignItems: "center" }}>
              <input
                type="checkbox"
                checked={continuityOn}
                onChange={(e) => setContinuityOn(e.target.checked)}
              />
              Bind generate batch to continuity
            </label>
            {replacePanelId ? <span className="pill warn">Replacing storyboard panel</span> : null}
          </div>
          <SpatialReferenceFieldset
            projectId={project.id}
            value={{ spatialMapId, spatialMapVersion, spatialCameraId }}
            onChange={(patch) => {
              if ("spatialMapId" in patch) setSpatialMapId(patch.spatialMapId);
              if ("spatialMapVersion" in patch) setSpatialMapVersion(patch.spatialMapVersion);
              if ("spatialCameraId" in patch) setSpatialCameraId(patch.spatialCameraId);
            }}
            testIdPrefix="image"
          />
        </CisAccordion>

        <CisAccordion
          id="prompt-intelligence"
          title="Prompt Intelligence"
          persistKey={accordionKey}
          status={piStatus}
          className="cis-pi"
        >
          <PromptIntelligencePanel
            projectId={project.id}
            domain="image"
            creatorPrompt={effectivePrompt(prompt, controls)}
            negativePrompt={negative}
            sceneId={sceneId || undefined}
            providerId={
              generateTargets[0]?.providerPreference || bestMatch?.providerPreference || "comfyui"
            }
            modelId={generateTargets[0]?.modelId || bestMatch?.modelId || bestMatch?.family || "qwen2512"}
            onApply={(payload) => setPrompt(payload.finalProviderPrompt)}
            onArtistStatusChange={setPiStatus}
            artistLayout
          />
        </CisAccordion>

        {/* Generate CTA */}
        <section className="cis-generate-cta">
          <button
            type="button"
            className="primary cis-generate-cta__button"
            disabled={busy || !prompt.trim()}
            onClick={() => void generate()}
            data-testid="cis-generate"
          >
            {busy ? "Generating…" : "Generate Images"}
          </button>
          <div className="cis-generate-cta__meta">
            <span>
              Estimated Time · <strong>{estimateTimeLabel(generateTargets, batchSize)}</strong>
            </span>
            <span>
              Using ·{" "}
              <strong>
                {mode === "all_models"
                  ? `${generateTargets.length} model${generateTargets.length === 1 ? "" : "s"} selected`
                  : generateTargets[0]?.displayName || "No model selected"}
              </strong>
            </span>
            {undoPanelId ? (
              <button type="button" className="ghost" onClick={() => void undoStoryboardAdd()}>
                Undo storyboard add
              </button>
            ) : null}
          </div>
        </section>

        <details
          className="cis-card"
          open={advancedOpen}
          onToggle={(e) => setAdvancedOpen((e.target as HTMLDetailsElement).open)}
        >
          <summary>Advanced</summary>
          <div className="cis-row" style={{ marginTop: "0.75rem" }}>
            <div className="field">
              <label>Negative</label>
              <input value={negative} onChange={(e) => setNegative(e.target.value)} />
            </div>
            <div className="field">
              <label>Seed</label>
              <input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} />
            </div>
            <div className="field">
              <label>Steps</label>
              <input
                type="number"
                value={steps}
                onChange={(e) => setSteps(e.target.value === "" ? "" : Number(e.target.value))}
              />
            </div>
            <div className="field">
              <label>Guidance</label>
              <input
                type="number"
                step="0.1"
                value={guidance}
                onChange={(e) => setGuidance(e.target.value === "" ? "" : Number(e.target.value))}
              />
            </div>
          </div>
        </details>

        {/* Results */}
        <section className="cis-results">
          <h2>Results</h2>
          {!groupedResults.length ? (
            <div className="cis-empty-results" data-testid="cis-empty-results">
              <div className="cis-empty-results__art" aria-hidden />
              <h3>No images generated yet</h3>
              <p>
                Describe your shot, select references, and click <strong>Generate Images</strong>.
              </p>
            </div>
          ) : (
            groupedResults.map(([group, cards]) => (
              <div key={group} className="cis-result-group">
                <h3>{group}</h3>
                <div className="cis-result-grid">
                  {cards.map((card) => {
                    const providerName =
                      allProviders.find((p) => p.id === card.providerId)?.displayName ||
                      providers.find((p) => p.id === card.providerId)?.displayName ||
                      card.family ||
                      "Image";
                    return (
                      <article key={card.jobId} className="cis-result-card">
                        {card.assetId ? (
                          <img src={api.assetUrl(card.assetId)} alt="" />
                        ) : (
                          <div className="cis-result-pending">{card.status}</div>
                        )}
                        <div className="cis-result-card__meta">
                          <span>{providerName}</span>
                          <span>{card.elapsedSec ? `${card.elapsedSec} sec` : card.status}</span>
                        </div>
                        <div className="cis-result-actions">
                          {card.assetId && (
                            <>
                              <button type="button" onClick={() => void approveImage(card.assetId!)}>
                                Use
                              </button>
                              <button type="button" onClick={() => void addToStoryboard(card.assetId!)}>
                                Storyboard
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  setRefIds((prev) => Array.from(new Set([card.assetId!, ...prev])));
                                  setMsg("Set as variation reference.");
                                }}
                              >
                                Variation
                              </button>
                              <button type="button" onClick={() => setStudioMode("edit")}>
                                Edit
                              </button>
                              <button type="button" onClick={() => void reopenFromAsset(card.assetId!)}>
                                More…
                              </button>
                            </>
                          )}
                          {card.status === "failed" && !card.assetId && (
                            <span className="muted tiny">Provider failed — batch continued</span>
                          )}
                        </div>
                      </article>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </section>
      </div>
    </div>
  );
}
