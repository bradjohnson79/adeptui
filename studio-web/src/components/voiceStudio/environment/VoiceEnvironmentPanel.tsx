import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../../api";
import type {
  VoiceEnvironmentProfile,
  VoiceEnvironmentRecommendation,
  VoiceEnvironmentRender,
  VoiceEnvironmentSource,
  VoiceStudioWorkspaceTab,
} from "../../../contracts/voiceEnvironment";
import type {
  VoicePerformanceRecord,
  VoicePerformanceTake,
} from "../../../contracts/voicePerformanceM410";
import { HelpTip, PanelHeading } from "../../HelpTip";
import { GlobalScopeField } from "../../creator/GlobalScopeField";
import { AddFromProjectLibraryModal } from "../../timeline-master/AddFromProjectLibraryModal";
import { Button } from "../../ui";
import type { Project } from "../../../types";
import { pickCanonicalVoiceRecord } from "../canonicalVoiceRecord";
import {
  DEVICE_PRESETS,
  DIRECTION_PRESETS,
  DISTANCE_PRESETS,
  SPACE_PRESETS,
  TONE_PRESETS,
  WALLA_PRESETS,
  type PresetOption,
} from "./presets";

type VoiceIdentitySummary = {
  id: string;
  name: string;
  version?: string | number | null;
};

type VoiceEnvironmentPanelProps = {
  projectId: string;
  characterId: string;
  characterName: string;
  approvedVoiceIdentity?: VoiceIdentitySummary | null;
  onMsg: (message: string) => void;
  onSelectStage: (tab: VoiceStudioWorkspaceTab) => void;
  initialLibraryAssetId?: string;
};

type VoiceEnvironmentDraft = {
  name: string;
  sceneId: string;
  locationId: string;
  spacePreset: string;
  customSpacePrompt: string;
  distancePreset: string;
  customDistancePrompt: string;
  directionPreset: string;
  customDirectionPrompt: string;
  tonePreset: string;
  customTonePrompt: string;
  devicePreset: string;
  customDevicePrompt: string;
  wallaPreset: string;
  wallaLevel: "" | "subtle" | "moderate" | "present";
  wallaDistance: "" | "near" | "mid" | "far";
  wallaBehavior: "" | "steady" | "reactive" | "intermittent";
  customWallaPrompt: string;
  source: VoiceEnvironmentSource;
};

type RuntimeStatus = {
  ok: boolean;
  message?: string;
  status?: string;
};

const WALLA_LEVELS = [
  { id: "subtle", label: "Subtle" },
  { id: "moderate", label: "Moderate" },
  { id: "present", label: "Present" },
] as const;

const WALLA_DISTANCES = [
  { id: "near", label: "Near" },
  { id: "mid", label: "Mid" },
  { id: "far", label: "Far" },
] as const;

const WALLA_BEHAVIORS = [
  { id: "steady", label: "Steady" },
  { id: "reactive", label: "Reactive" },
  { id: "intermittent", label: "Intermittent" },
] as const;

function createDefaultDraft(characterName: string): VoiceEnvironmentDraft {
  return {
    name: `${characterName} Scene Environment`,
    sceneId: "",
    locationId: "",
    spacePreset: "small_room",
    customSpacePrompt: "",
    distancePreset: "medium_close_up",
    customDistancePrompt: "",
    directionPreset: "center",
    customDirectionPrompt: "",
    tonePreset: "natural",
    customTonePrompt: "",
    devicePreset: "direct",
    customDevicePrompt: "",
    wallaPreset: "none",
    wallaLevel: "",
    wallaDistance: "",
    wallaBehavior: "",
    customWallaPrompt: "",
    source: "manual",
  };
}

function draftFromProfile(profile: VoiceEnvironmentProfile): VoiceEnvironmentDraft {
  return {
    name: profile.name || "Scene Environment",
    sceneId: String(profile.sceneId || ""),
    locationId: String(profile.locationId || ""),
    spacePreset: profile.spacePreset || "small_room",
    customSpacePrompt: String(profile.customSpacePrompt || ""),
    distancePreset: profile.distancePreset || "medium_close_up",
    customDistancePrompt: String(profile.customDistancePrompt || ""),
    directionPreset: profile.directionPreset || "center",
    customDirectionPrompt: String(profile.customDirectionPrompt || ""),
    tonePreset: profile.tonePreset || "natural",
    customTonePrompt: String(profile.customTonePrompt || ""),
    devicePreset: profile.devicePreset || "direct",
    customDevicePrompt: String(profile.customDevicePrompt || ""),
    wallaPreset: profile.wallaPreset || "none",
    wallaLevel: (profile.wallaLevel || "") as VoiceEnvironmentDraft["wallaLevel"],
    wallaDistance: (profile.wallaDistance || "") as VoiceEnvironmentDraft["wallaDistance"],
    wallaBehavior: (profile.wallaBehavior || "") as VoiceEnvironmentDraft["wallaBehavior"],
    customWallaPrompt: String(profile.customWallaPrompt || ""),
    source: profile.source || "manual",
  };
}

function draftPayload(draft: VoiceEnvironmentDraft): Record<string, unknown> {
  return {
    name: draft.name.trim() || "Scene Environment",
    sceneId: draft.sceneId || undefined,
    locationId: draft.locationId || undefined,
    spacePreset: draft.spacePreset,
    customSpacePrompt: draft.customSpacePrompt.trim() || undefined,
    distancePreset: draft.distancePreset,
    customDistancePrompt: draft.customDistancePrompt.trim() || undefined,
    directionPreset: draft.directionPreset,
    customDirectionPrompt: draft.customDirectionPrompt.trim() || undefined,
    tonePreset: draft.tonePreset,
    customTonePrompt: draft.customTonePrompt.trim() || undefined,
    devicePreset: draft.devicePreset,
    customDevicePrompt: draft.customDevicePrompt.trim() || undefined,
    wallaPreset: draft.wallaPreset,
    wallaLevel: draft.wallaLevel || undefined,
    wallaDistance: draft.wallaDistance || undefined,
    wallaBehavior: draft.wallaBehavior || undefined,
    customWallaPrompt: draft.customWallaPrompt.trim() || undefined,
    source: draft.source,
  };
}

function pickRecord(
  records: VoicePerformanceRecord[],
  characterId: string,
  voiceIdentityId?: string | null,
): VoicePerformanceRecord | null {
  return pickCanonicalVoiceRecord(records, characterId, voiceIdentityId, { requireApprovedTake: true });
}

function optionLabel(options: readonly PresetOption[], id: string) {
  return options.find((option) => option.id === id)?.label || id;
}

function renderStatusLabel(render: VoiceEnvironmentRender) {
  if (render.approved) return "Approved";
  if (render.status === "preview_ready") return "Preview Ready";
  if (render.status === "completed") return "Rendered";
  return render.status.replace(/_/g, " ");
}

function ControlGroup({
  title,
  tip,
  options,
  value,
  onChange,
  customValue,
  onCustomChange,
  testId,
}: {
  title: string;
  tip: string;
  options: readonly PresetOption[];
  value: string;
  onChange: (value: string) => void;
  customValue: string;
  onCustomChange: (value: string) => void;
  testId: string;
}) {
  return (
    <section className="voice-environment-panel__control" data-testid={testId}>
      <div className="voice-performance-studio__field">
        <span>
          {title}
          <HelpTip label={title} content={tip} />
        </span>
        <div className="voice-studio-chip-row">
          {options.map((option) => (
            <button
              key={option.id}
              type="button"
              className={`voice-studio-chip${value === option.id ? " selected" : ""}`}
              onClick={() => onChange(option.id)}
            >
              {option.label}
            </button>
          ))}
        </div>
        {value === "custom" ? (
          <textarea
            rows={2}
            value={customValue}
            onChange={(event) => onCustomChange(event.target.value)}
            placeholder={`Describe the ${title.toLowerCase()} in plain language`}
          />
        ) : null}
        <p className="muted">{options.find((option) => option.id === value)?.description}</p>
      </div>
    </section>
  );
}

export function VoiceEnvironmentPanel({
  projectId,
  characterId,
  characterName,
  approvedVoiceIdentity,
  onMsg,
  onSelectStage,
  initialLibraryAssetId,
}: VoiceEnvironmentPanelProps) {
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatus | null>(null);
  const [record, setRecord] = useState<VoicePerformanceRecord | null>(null);
  const [approvedTake, setApprovedTake] = useState<VoicePerformanceTake | null>(null);
  const [libraryAssetId, setLibraryAssetId] = useState(initialLibraryAssetId || "");
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [hearOriginal, setHearOriginal] = useState(true);
  const [profiles, setProfiles] = useState<VoiceEnvironmentProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState("");
  const [draft, setDraft] = useState<VoiceEnvironmentDraft>(() => createDefaultDraft(characterName));
  const [lastSavedSnapshot, setLastSavedSnapshot] = useState("");
  const processedPlayerRef = useRef<HTMLAudioElement | null>(null);
  const [renders, setRenders] = useState<VoiceEnvironmentRender[]>([]);
  const [selectedRenderId, setSelectedRenderId] = useState("");
  const [recommendation, setRecommendation] = useState<VoiceEnvironmentRecommendation | null>(null);
  const [compareOpen, setCompareOpen] = useState(false);
  const [busyAction, setBusyAction] = useState("");
  const [isGlobal, setIsGlobal] = useState(false);

  const hasApprovedVoiceIdentity = Boolean(approvedVoiceIdentity?.id);
  const currentSnapshot = JSON.stringify(draftPayload(draft));
  const isDirty = Boolean(selectedProfileId) && currentSnapshot !== lastSavedSnapshot;

  const activeRenders = useMemo(() => {
    const filtered = selectedProfileId
      ? renders.filter((render) => render.environmentProfileId === selectedProfileId)
      : renders;
    return [...filtered].sort((a, b) => String(b.updatedAt || "").localeCompare(String(a.updatedAt || "")));
  }, [renders, selectedProfileId]);

  const currentRender = useMemo(
    () => activeRenders.find((render) => render.id === selectedRenderId) || activeRenders[0] || null,
    [activeRenders, selectedRenderId],
  );

  const comparisonRenders = useMemo(() => activeRenders.slice(0, 2), [activeRenders]);

  const applyProfile = useCallback((profile: VoiceEnvironmentProfile) => {
    setSelectedProfileId(profile.id);
    const nextDraft = draftFromProfile(profile);
    setDraft(nextDraft);
    setLastSavedSnapshot(JSON.stringify(draftPayload(nextDraft)));
  }, []);

  const refreshPerformanceContext = useCallback(async () => {
    if (!hasApprovedVoiceIdentity) {
      setRecord(null);
      setApprovedTake(null);
      return;
    }
    const response = await api.voicePerformanceM410.listProjectRecords(projectId);
    const preferred = pickRecord(response.records || [], characterId, approvedVoiceIdentity?.id);
    setRecord(preferred);
    if (!preferred?.approvedTakeId) {
      setApprovedTake(null);
      return;
    }
    setApprovedTake(preferred.takes.find((take) => take.id === preferred.approvedTakeId) || null);
  }, [approvedVoiceIdentity?.id, characterId, hasApprovedVoiceIdentity, projectId]);

  const refreshProfiles = useCallback(async () => {
    const nextProfiles = await api.voiceEnvironment.listProfiles(projectId, characterId);
    const sorted = [...nextProfiles].sort((a, b) => String(b.updatedAt || "").localeCompare(String(a.updatedAt || "")));
    setProfiles(sorted);
    if (!sorted.length) {
      const nextDraft = createDefaultDraft(characterName);
      setSelectedProfileId("");
      setDraft(nextDraft);
      setLastSavedSnapshot("");
      return;
    }
    const selected = sorted.find((profile) => profile.id === selectedProfileId) || sorted[0];
    applyProfile(selected);
  }, [applyProfile, characterId, characterName, projectId, selectedProfileId]);

  const refreshRenders = useCallback(async () => {
    if (!approvedTake?.id) {
      setRenders([]);
      setSelectedRenderId("");
      return;
    }
    const nextRenders = await api.voiceEnvironment.listRenders(projectId, {
      characterId,
      performanceTakeId: approvedTake.id,
    });
    const sorted = [...nextRenders].sort((a, b) => String(b.updatedAt || "").localeCompare(String(a.updatedAt || "")));
    setRenders(sorted);
    setSelectedRenderId((current) => current || sorted[0]?.id || "");
  }, [approvedTake?.id, characterId, projectId]);

  useEffect(() => {
    void (async () => {
      try {
        const status = await api.voiceEnvironment.runtimeStatus();
        setRuntimeStatus(status as RuntimeStatus);
      } catch {
        setRuntimeStatus(null);
      }
    })();
  }, []);

  useEffect(() => {
    void refreshPerformanceContext().catch((error: any) => {
      onMsg(error?.message || "Voice Performance records could not be loaded.");
    });
  }, [onMsg, refreshPerformanceContext]);

  useEffect(() => {
    void refreshProfiles().catch((error: any) => {
      onMsg(error?.message || "Voice Environment profiles could not be loaded.");
    });
  }, [onMsg, refreshProfiles]);

  useEffect(() => {
    void refreshRenders().catch((error: any) => {
      onMsg(error?.message || "Voice Environment renders could not be loaded.");
    });
  }, [onMsg, refreshRenders]);

  const saveProfile = useCallback(async () => {
    setBusyAction("save");
    try {
      const payload = {
        projectId,
        characterId,
        ...draftPayload(draft),
      };
      const profile = selectedProfileId
        ? await api.voiceEnvironment.updateProfile(selectedProfileId, payload)
        : await api.voiceEnvironment.createProfile(payload);
      applyProfile(profile);
      await refreshProfiles();
      onMsg("Voice Environment profile saved.");
      return profile;
    } catch (error: any) {
      onMsg(error?.message || "Voice Environment profile could not be saved.");
      return null;
    } finally {
      setBusyAction("");
    }
  }, [applyProfile, characterId, draft, onMsg, projectId, refreshProfiles, selectedProfileId]);

  const requestRecommendation = useCallback(async () => {
    setBusyAction("recommend");
    try {
      const next = await api.voiceEnvironment.recommend({
        projectId,
        characterId,
        sceneId: draft.sceneId || record?.sceneId || undefined,
        locationId: draft.locationId || undefined,
      });
      setRecommendation(next);
      setDraft((current) => ({
        ...current,
        name: String(next.profileDraft.name || current.name),
        sceneId: String(next.profileDraft.sceneId || current.sceneId || ""),
        locationId: String(next.profileDraft.locationId || current.locationId || ""),
        spacePreset: String(next.profileDraft.spacePreset || current.spacePreset),
        customSpacePrompt: String(next.profileDraft.customSpacePrompt || current.customSpacePrompt || ""),
        distancePreset: String(next.profileDraft.distancePreset || current.distancePreset),
        customDistancePrompt: String(next.profileDraft.customDistancePrompt || current.customDistancePrompt || ""),
        directionPreset: String(next.profileDraft.directionPreset || current.directionPreset),
        customDirectionPrompt: String(next.profileDraft.customDirectionPrompt || current.customDirectionPrompt || ""),
        tonePreset: String(next.profileDraft.tonePreset || current.tonePreset),
        customTonePrompt: String(next.profileDraft.customTonePrompt || current.customTonePrompt || ""),
        devicePreset: String(next.profileDraft.devicePreset || current.devicePreset),
        customDevicePrompt: String(next.profileDraft.customDevicePrompt || current.customDevicePrompt || ""),
        wallaPreset: String(next.profileDraft.wallaPreset || current.wallaPreset),
        wallaLevel: (next.profileDraft.wallaLevel
          ? String(next.profileDraft.wallaLevel)
          : current.wallaLevel) as VoiceEnvironmentDraft["wallaLevel"],
        wallaDistance: (next.profileDraft.wallaDistance
          ? String(next.profileDraft.wallaDistance)
          : current.wallaDistance) as VoiceEnvironmentDraft["wallaDistance"],
        wallaBehavior: (next.profileDraft.wallaBehavior
          ? String(next.profileDraft.wallaBehavior)
          : current.wallaBehavior) as VoiceEnvironmentDraft["wallaBehavior"],
        customWallaPrompt: String(next.profileDraft.customWallaPrompt || current.customWallaPrompt || ""),
        source: "codirector",
      }));
      onMsg("Co-Director recommended a scene acoustic starting point.");
    } catch (error: any) {
      onMsg(error?.message || "Co-Director could not recommend a scene acoustic yet.");
    } finally {
      setBusyAction("");
    }
  }, [characterId, draft.locationId, draft.sceneId, onMsg, projectId, record?.sceneId]);

  const runRenderAction = useCallback(
    async (mode: "preview" | "render") => {
      if (!libraryAssetId && !(record?.id && approvedTake?.id)) {
        onMsg("Select a recording from the Library.");
        return;
      }
      if (runtimeStatus && runtimeStatus.ok === false) {
        onMsg(runtimeStatus.message || "Voice Environment processing is not ready yet.");
        return;
      }
      setBusyAction(mode);
      try {
        // ORDER 4: auto-apply draft filters so Preview/Render work without requiring Save first.
        let profileId = selectedProfileId;
        if (!profileId || isDirty) {
          const payload = {
            projectId,
            characterId,
            ...draftPayload(draft),
          };
          const profile = profileId
            ? await api.voiceEnvironment.updateProfile(profileId, payload)
            : await api.voiceEnvironment.createProfile(payload);
          applyProfile(profile);
          await refreshProfiles();
          profileId = profile.id;
        }
        if (!profileId) {
          onMsg("Could not apply environment filters for processing.");
          return;
        }
        const next =
          mode === "preview"
            ? await api.voiceEnvironment.preview({
                projectId,
                characterId,
                performanceRecordId: libraryAssetId ? "" : record?.id,
                performanceTakeId: libraryAssetId ? "" : approvedTake?.id,
                libraryAssetId,
                environmentProfileId: profileId,
                preview: true,
              })
            : await api.voiceEnvironment.render({
                projectId,
                characterId,
                performanceRecordId: libraryAssetId ? "" : record?.id,
                performanceTakeId: libraryAssetId ? "" : approvedTake?.id,
                libraryAssetId,
                environmentProfileId: profileId,
                preview: false,
              });
        setSelectedRenderId(next.id);
        await refreshRenders();
        onMsg(mode === "preview" ? "Environment preview ready." : "Final take saved. The original recording is unchanged.");
      } catch (error: any) {
        onMsg(error?.message || "Voice Environment processing failed.");
      } finally {
        setBusyAction("");
      }
    },
    [
      applyProfile,
      approvedTake?.id,
      libraryAssetId,
      record?.id,
      characterId,
      draft,
      isDirty,
      onMsg,
      projectId,
      record?.id,
      refreshProfiles,
      refreshRenders,
      runtimeStatus,
      selectedProfileId,
    ],
  );


  useEffect(() => {
    const el = processedPlayerRef.current;
    if (!el || !currentRender?.processedAudioAssetId) return;
    if (busyAction === "preview" || busyAction === "render") return;
    // Autoplay latest environment pass after Preview/Render completes (user gesture already started the action).
    void el.play().catch(() => {
      /* browser may still block; controls remain */
    });
  }, [busyAction, currentRender?.id, currentRender?.processedAudioAssetId]);

  const approveRender = useCallback(async () => {
    if (!currentRender?.id) {
      onMsg("Preview or render the environment first.");
      return;
    }
    setBusyAction("approve");
    try {
      await api.voiceEnvironment.approve(currentRender.id, true, { isGlobal });
      await refreshRenders();
      onMsg(
        isGlobal
          ? "Voice Environment approved and saved to Global Library (available in every project)."
          : "Voice Environment approved and saved to this project's Library.",
      );
    } catch (error: any) {
      onMsg(error?.message || "Voice Environment approval failed.");
    } finally {
      setBusyAction("");
    }
  }, [currentRender?.id, isGlobal, onMsg, refreshRenders]);

  useEffect(() => {
    if (initialLibraryAssetId) setLibraryAssetId(initialLibraryAssetId);
  }, [initialLibraryAssetId]);

  const openInAudioStudio = useCallback(async () => {
    if (!currentRender?.id) {
      onMsg("Render an environment version first.");
      return;
    }
    setBusyAction("audiostudio");
    try {
      await api.voiceEnvironment.openAudioStudio(currentRender.id);
      const url = new URL(window.location.href);
      url.searchParams.set("workspace", "audiostudio");
      window.history.pushState({}, "", url.toString());
      window.dispatchEvent(new PopStateEvent("popstate"));
      onMsg("Opened Audio Studio with environment stems.");
    } catch (error: any) {
      onMsg(error?.message || "Could not open Audio Studio.");
    } finally {
      setBusyAction("");
    }
  }, [currentRender?.id, onMsg]);

  const dryAssetId = libraryAssetId || approvedTake?.audioAssetId || "";

  return (
    <section className="panel voice-performance-studio voice-environment-panel" data-testid="voice-environment-panel">
      <header className="voice-performance-studio__header">
        <PanelHeading
          title={`Voice Environment — ${characterName}`}
          tip="Shape where the approved take sits in the scene: the room, distance, direction, tone, device, and background voices."
          as="h3"
        />
        <div className="voice-performance-studio__meta">
          <div className="voice-studio-actions">
            <Button type="button" data-testid="voice-environment-library" onClick={() => setLibraryOpen(true)}>
              Select from Library
            </Button>
            <Button type="button" data-testid="voice-environment-hear" onClick={() => setHearOriginal((current) => !current)}>
              {hearOriginal ? "Hear processed" : "Hear original"}
            </Button>
          </div>
          {runtimeStatus?.message ? <p className="muted">{runtimeStatus.message}</p> : null}
        </div>
      </header>

      <div className="voice-environment-panel__layout">
        <section className="voice-performance-studio__takes voice-environment-panel__preview">
          <PanelHeading
            title="Scene Preview"
            tip="Listen to the approved dry take beside the latest environment pass so you can judge whether the performance still feels clear and intentional."
            as="h4"
          />

          <article className="voice-studio-candidate-card">
            <strong>Original</strong>
            <p className="muted">
              The Library recording stays unchanged. Environment processing makes a new version.
            </p>
            {dryAssetId && hearOriginal ? (
              <audio controls src={api.assetUrl(dryAssetId, undefined, projectId)} data-testid="voice-environment-dry-player" />
            ) : (
              <p className="muted">{dryAssetId ? "Original is ready." : "Select a recording from the Library."}</p>
            )}
          </article>

          <article className="voice-studio-candidate-card">
            <strong>Current Environment Pass</strong>
            <p className="muted">
              {currentRender
                ? `${optionLabel(SPACE_PRESETS, draft.spacePreset)} · ${optionLabel(DISTANCE_PRESETS, draft.distancePreset)} · ${optionLabel(DIRECTION_PRESETS, draft.directionPreset)}`
                : "Preview or Render to hear the scene acoustic. Filter changes apply without Save."}
            </p>
            {currentRender?.processedAudioAssetId && !hearOriginal ? (
              <audio
                ref={processedPlayerRef}
                controls
                src={api.assetUrl(currentRender.processedAudioAssetId, undefined, projectId)}
                data-testid="voice-environment-processed-player"
              />
            ) : (
              <div className="voice-studio-empty-player">No environment pass yet.</div>
            )}
            {currentRender ? (
              <div className="voice-environment-panel__timing">
                <span className="pill">{renderStatusLabel(currentRender)}</span>
                <span className="pill">
                  Speech start {Math.round(Number(currentRender.timing?.speechStartOffsetMs || 0))} ms
                </span>
                <span className="pill">
                  Tail {Math.round(Number(currentRender.timing?.tailDurationMs || 0))} ms
                </span>
              </div>
            ) : null}
          </article>

          <div className="voice-studio-actions">
            <Button
              type="button"
              disabled={busyAction === "preview" || busyAction === "render" || busyAction === "save"}
              onClick={() => void runRenderAction("preview")}
              data-testid="voice-environment-preview"
            >
              Preview
            </Button>
            <Button
              type="button"
              disabled={comparisonRenders.length < 2}
              onClick={() => {
                if (comparisonRenders.length < 2) {
                  onMsg("Create at least two environment passes to compare A/B.");
                  return;
                }
                setCompareOpen((current) => !current);
              }}
              data-testid="voice-environment-ab"
            >
              A/B
            </Button>
            <Button
              type="button"
              disabled={busyAction === "save"}
              onClick={() => void saveProfile()}
              data-testid="voice-environment-save-profile"
            >
              Save Profile
            </Button>
            <Button
              type="button"
              variant="primary"
              className="voice-studio-primary-cta"
              disabled={busyAction === "preview" || busyAction === "render" || busyAction === "save"}
              onClick={() => void runRenderAction("render")}
              data-testid="voice-environment-render"
            >
              Save Final Take
            </Button>
            <GlobalScopeField
              testId="voice-environment-global"
              checked={isGlobal}
              onChange={setIsGlobal}
            />
            <Button
              type="button"
              disabled={!currentRender || busyAction === "approve"}
              onClick={() => void approveRender()}
              data-testid="voice-environment-approve"
            >
              Approve
            </Button>
            <Button
              type="button"
              disabled={!currentRender || Boolean(busyAction)}
              onClick={() => void openInAudioStudio()}
              data-testid="voice-environment-audio-studio"
            >
              Open in Audio Studio
            </Button>
          </div>

          {compareOpen ? (
            <div className="voice-studio-gallery" data-testid="voice-environment-ab-panel">
              {comparisonRenders.map((render, index) => (
                <article
                  key={render.id}
                  className={`voice-studio-candidate-card${selectedRenderId === render.id ? " selected" : ""}`}
                >
                  <div className="voice-performance-studio__take-header">
                    <strong>{index === 0 ? "Pass A" : "Pass B"}</strong>
                    <span className="pill">{renderStatusLabel(render)}</span>
                  </div>
                  <p className="muted">
                    {optionLabel(SPACE_PRESETS, draft.spacePreset)} · {optionLabel(DISTANCE_PRESETS, draft.distancePreset)}
                  </p>
                  {render.processedAudioAssetId ? <audio controls src={api.assetUrl(render.processedAudioAssetId)} /> : null}
                  <Button type="button" onClick={() => setSelectedRenderId(render.id)}>
                    Use This Pass
                  </Button>
                </article>
              ))}
            </div>
          ) : null}

          {recommendation ? (
            <article className="voice-studio-candidate-card" data-testid="voice-environment-recommendation">
              <strong>Co-Director Recommendation</strong>
              <p>{recommendation.reason}</p>
              <p className="muted">
                {recommendation.spaceLabel} · {recommendation.distanceLabel} · {recommendation.directionLabel} ·{" "}
                {recommendation.toneLabel}
              </p>
            </article>
          ) : null}
        </section>

        <section className="voice-performance-studio__performance-panel voice-environment-panel__controls">
          <PanelHeading
            title="Environment Controls"
            tip="Use creator-friendly controls to place the voice in the scene. Keep technical audio jargon hidden; focus on what the audience should feel."
            as="h4"
          />

          <div className="voice-performance-studio__direction">
            <span className="voice-performance-studio__label">Direction Mode</span>
            <div className="workspace-tabs" role="tablist">
              <button
                type="button"
                role="tab"
                aria-selected={draft.source === "codirector"}
                className={draft.source === "codirector" ? "primary" : ""}
                onClick={() => setDraft((current) => ({ ...current, source: "codirector" }))}
              >
                Co-Director Recommended
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={draft.source === "manual"}
                className={draft.source === "manual" ? "primary" : ""}
                onClick={() => setDraft((current) => ({ ...current, source: "manual" }))}
              >
                Manual
              </button>
            </div>
            <div className="voice-studio-actions">
              <Button
                type="button"
                disabled={busyAction === "recommend"}
                onClick={() => void requestRecommendation()}
                data-testid="voice-environment-recommend"
              >
                Ask Co-Director
              </Button>
            </div>
          </div>

          <label className="voice-performance-studio__field">
            <span>
              Environment Profile Name
              <HelpTip
                label="Environment Profile Name"
                content="Save favorite scene acoustics as reusable profiles so you can come back to them later."
              />
            </span>
            <input
              value={draft.name}
              onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
              data-testid="voice-environment-name"
            />
          </label>

          {profiles.length ? (
            <label className="voice-performance-studio__field">
              <span>
                Saved Profiles
                <HelpTip
                  label="Saved Profiles"
                  content="Switch between saved environment looks for this character without losing your approved performance."
                />
              </span>
              <select
                value={selectedProfileId}
                onChange={(event) => {
                  const profile = profiles.find((item) => item.id === event.target.value);
                  if (profile) applyProfile(profile);
                }}
                data-testid="voice-environment-profile-select"
              >
                {profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          <div className="voice-performance-studio__grid">
            <ControlGroup
              title="Space"
              tip="Choose the kind of place the voice should live in, from intimate rooms to huge spaces."
              options={SPACE_PRESETS}
              value={draft.spacePreset}
              onChange={(value) => setDraft((current) => ({ ...current, spacePreset: value }))}
              customValue={draft.customSpacePrompt}
              onCustomChange={(value) => setDraft((current) => ({ ...current, customSpacePrompt: value }))}
              testId="voice-environment-space"
            />
            <ControlGroup
              title="Distance"
              tip="Decide how close the speaker feels to the listener inside the scene."
              options={DISTANCE_PRESETS}
              value={draft.distancePreset}
              onChange={(value) => setDraft((current) => ({ ...current, distancePreset: value }))}
              customValue={draft.customDistancePrompt}
              onCustomChange={(value) => setDraft((current) => ({ ...current, customDistancePrompt: value }))}
              testId="voice-environment-distance"
            />
          </div>

          <section className="voice-environment-panel__control" data-testid="voice-environment-direction">
            <div className="voice-performance-studio__field">
              <span>
                Direction
                <HelpTip
                  label="Direction"
                  content="Place the voice around the listener so it feels grounded in the scene, not stuck in the center by default."
                />
              </span>
              <div className="voice-environment-panel__stage" data-testid="voice-environment-stage-grid">
                {DIRECTION_PRESETS.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    className={`voice-studio-chip${draft.directionPreset === option.id ? " selected" : ""}`}
                    onClick={() => setDraft((current) => ({ ...current, directionPreset: option.id }))}
                    data-testid={option.id === "center" ? "voice-environment-stage" : undefined}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              {draft.directionPreset === "custom" ? (
                <textarea
                  rows={2}
                  value={draft.customDirectionPrompt}
                  onChange={(event) => setDraft((current) => ({ ...current, customDirectionPrompt: event.target.value }))}
                  placeholder="Describe where the voice should come from"
                />
              ) : null}
              <p className="muted">{optionLabel(DIRECTION_PRESETS, draft.directionPreset)}</p>
            </div>
          </section>

          <div className="voice-performance-studio__grid">
            <ControlGroup
              title="Tone"
              tip="Shape how the voice color changes once it lives in the scene."
              options={TONE_PRESETS}
              value={draft.tonePreset}
              onChange={(value) => setDraft((current) => ({ ...current, tonePreset: value }))}
              customValue={draft.customTonePrompt}
              onCustomChange={(value) => setDraft((current) => ({ ...current, customTonePrompt: value }))}
              testId="voice-environment-tone"
            />
            <ControlGroup
              title="Device"
              tip="Choose whether the voice is heard directly in the space or through a phone, radio, intercom, or another device."
              options={DEVICE_PRESETS}
              value={draft.devicePreset}
              onChange={(value) => setDraft((current) => ({ ...current, devicePreset: value }))}
              customValue={draft.customDevicePrompt}
              onCustomChange={(value) => setDraft((current) => ({ ...current, customDevicePrompt: value }))}
              testId="voice-environment-device"
            />
          </div>

          <section className="voice-environment-panel__control" data-testid="voice-environment-walla">
            <div className="voice-performance-studio__field">
              <span>
                Walla
                <HelpTip
                  label="Walla"
                  content="Add background voices when the scene needs people nearby. Keep it subtle unless the environment should feel busy."
                />
              </span>
              <div className="voice-studio-chip-row">
                {WALLA_PRESETS.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    className={`voice-studio-chip${draft.wallaPreset === option.id ? " selected" : ""}`}
                    onClick={() => setDraft((current) => ({ ...current, wallaPreset: option.id }))}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <div className="voice-performance-studio__advanced-grid">
                <label className="voice-performance-studio__field">
                  <span>Level</span>
                  <select
                    value={draft.wallaLevel}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        wallaLevel: event.target.value as VoiceEnvironmentDraft["wallaLevel"],
                      }))
                    }
                  >
                    <option value="">Auto</option>
                    {WALLA_LEVELS.map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="voice-performance-studio__field">
                  <span>Distance</span>
                  <select
                    value={draft.wallaDistance}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        wallaDistance: event.target.value as VoiceEnvironmentDraft["wallaDistance"],
                      }))
                    }
                  >
                    <option value="">Auto</option>
                    {WALLA_DISTANCES.map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="voice-performance-studio__field">
                  <span>Behavior</span>
                  <select
                    value={draft.wallaBehavior}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        wallaBehavior: event.target.value as VoiceEnvironmentDraft["wallaBehavior"],
                      }))
                    }
                  >
                    <option value="">Auto</option>
                    {WALLA_BEHAVIORS.map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              {draft.wallaPreset === "custom" ? (
                <textarea
                  rows={2}
                  value={draft.customWallaPrompt}
                  onChange={(event) => setDraft((current) => ({ ...current, customWallaPrompt: event.target.value }))}
                  placeholder="Describe the background voices and activity"
                />
              ) : null}
              <p className="muted">{WALLA_PRESETS.find((option) => option.id === draft.wallaPreset)?.description}</p>
            </div>
          </section>

          <p className="muted">
            {isDirty
              ? "Unsaved filter changes — Preview and Render will use them immediately."
              : selectedProfileId
                ? "This environment profile is saved."
                : "Adjust filters, then Preview or Save Final Take. The original recording stays in the Library."}
          </p>
        </section>
      </div>
      {libraryOpen ? (
        <AddFromProjectLibraryModal
          project={{ id: projectId, name: characterName, assets: [] } as Project}
          alreadyIds={dryAssetId ? [dryAssetId] : []}
          mediaKind="audio"
          single
          onAdd={(ids) => {
            const next = ids[0] || "";
            setLibraryAssetId(next);
            setLibraryOpen(false);
            if (next) onMsg("Recording selected.");
          }}
          onClose={() => setLibraryOpen(false)}
        />
      ) : null}
    </section>
  );
}
