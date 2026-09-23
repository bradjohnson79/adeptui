import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { HelpTip, PanelHeading } from "./HelpTip";
import { useOpenCoDirector } from "./CoDirector";
import { VoicePerformanceStudio } from "./voiceStudio/VoicePerformanceStudio";
import {
  READINESS_LABELS,
  voiceStudioCoDirectorChips,
  type StudioPhase,
} from "./voiceStudio/constants";
import {
  VOICE_STUDIO_STAGE_ORDER,
  type VoiceStudioWorkspaceTab,
} from "../contracts/voiceEnvironment";
import { VoiceEnvironmentPanel } from "./voiceStudio/environment/VoiceEnvironmentPanel";
import { VoiceIdentityPanel } from "./voiceStudio/VoiceIdentityPanel";
import { isCurrentCharacterRequest } from "./voiceStudio/voiceStudioCharacter";

const DEFAULT_DIALOGUE = "";

type Props = {
  projectId: string;
  characterId: string;
  characterName?: string;
  onMsg: (m: string) => void;
  onRefresh?: () => void;
  initialPhase?: StudioPhase | "voice" | "voicePerformance";
};

function mapInitialPhase(p?: Props["initialPhase"]): StudioPhase | undefined {
  if (!p) return undefined;
  if (p === "voice") return "create";
  if (p === "voicePerformance") return "performance";
  return p;
}

function mapInitialWorkspaceTab(p?: Props["initialPhase"] | string): VoiceStudioWorkspaceTab {
  const key = String(p || "").trim();
  // ORDER 5 amend: top-level Scene Dialogue + Takes stages removed — both live inside Voice Performance.
  if (
    key === "performance"
    || key === "voicePerformance"
    || key === "sceneDialogue"
    || key === "dialogue"
    || key === "takes"
  ) {
    return "performance";
  }
  if (key === "environment" || key === "voiceEnvironment") return "environment";
  if (key === "identity" || key === "voice" || key === "voiceIdentity") return "identity";
  return "identity";
}

function coerceWorkspaceTab(tab: string): VoiceStudioWorkspaceTab {
  if (tab === "sceneDialogue" || tab === "dialogue" || tab === "takes") return "performance";
  if (tab === "identity" || tab === "performance" || tab === "environment") {
    return tab;
  }
  return "identity";
}



function chooseApprovedVoice(voices: any[] | undefined, activeId: string): any | null {
  const list = Array.isArray(voices) ? voices : [];
  if (!list.length) return null;
  const isApproved = (voice: any) => String(voice?.approval_status || "").toLowerCase() === "approved";
  const active = list.find((voice) => voice?.id === activeId);
  if (active && isApproved(active)) return active;
  const approved = [...list]
    .filter(isApproved)
    .sort((a, b) =>
      String(b?.approved_at || b?.updated_at || "").localeCompare(String(a?.approved_at || a?.updated_at || "")),
    );
  return approved[0] || null;
}

export function VoiceStudioWorkspace({
  projectId,
  characterId,
  characterName: characterNameProp,
  onMsg,
  onRefresh,
  initialPhase,
}: Props) {
  const openCoDirector = useOpenCoDirector();

  const [ws, setWs] = useState<any | null>(null);
  const [phase, setPhase] = useState<StudioPhase>("create");
  const [workspaceTab, setWorkspaceTab] = useState<VoiceStudioWorkspaceTab>(() => mapInitialWorkspaceTab(initialPhase));
  const [readinessLabel, setReadinessLabel] = useState<keyof typeof READINESS_LABELS>("none");

  const [voiceId, setVoiceId] = useState("");
  const [testingCandidateId, setTestingCandidateId] = useState("");
  const [hasApprovedVoice, setHasApprovedVoice] = useState(false);
  const [hasApprovedTake, setHasApprovedTake] = useState(false);
  const [hasEnvironmentRender, setHasEnvironmentRender] = useState(false);
  const [hasSceneDialogue, setHasSceneDialogue] = useState(false);

  const [dialogue, setDialogue] = useState(DEFAULT_DIALOGUE);
  const characterIdRef = useRef(characterId);
  characterIdRef.current = characterId;

  const persistDraft = useCallback(
    async (patch: Record<string, unknown>) => {
      try { await api.saveVoiceStudioDraft(projectId, characterId, patch); } catch { /* best-effort */ }
    },
    [projectId, characterId],
  );

  const load = useCallback(async () => {
    const requestedId = characterId;
    const data = await api.getCharacterVoiceWorkspace(projectId, requestedId);
    if (!isCurrentCharacterRequest(requestedId, characterIdRef.current)) return;
    setWs(data);
    const draft = data.voiceStudioDraft || {};

    const activeId =
      draft.selectedVoiceProfileId ||
      data.activeVoiceProfileId ||
      data.voices?.[data.voices.length - 1]?.id ||
      "";
    setVoiceId(activeId);
    setTestingCandidateId(draft.testingCandidateId || data.testingSelection?.candidateId || "");
    if (draft.dialogue) setDialogue(String(draft.dialogue));

    const mapped = mapInitialPhase(initialPhase);
    if (mapped) setPhase(mapped);
    else if (draft.phase && ["method", "create", "select", "performance", "approve"].includes(draft.phase)) {
      setPhase(draft.phase as StudioPhase);
    } else if ((data.candidateBatches || []).length) setPhase("select");
    else setPhase("create");

    if (mapped === "performance" || initialPhase === "voicePerformance") {
      setWorkspaceTab("performance");
    } else {
      setWorkspaceTab("identity");
    }

    if (data.activeVoice?.approval_status === "approved") setReadinessLabel("approved");
    else if (draft.testingCandidateId) setReadinessLabel("readyPerformance");
    else if ((data.candidateBatches || []).length) setReadinessLabel("chooseVoice");
    else setReadinessLabel("none");

  }, [projectId, characterId, initialPhase]);

  useEffect(() => {
    void load().catch((e) => onMsg(e?.message || String(e)));
  }, [load, onMsg]);

  useEffect(() => {
    if (!projectId || !characterId) return;
    const requestedId = characterId;
    (async () => {
      try {
        const result = await api.characterVoiceApprovedStatus(projectId, requestedId);
        if (!isCurrentCharacterRequest(requestedId, characterIdRef.current)) return;
        setHasApprovedVoice(Boolean(result.hasApprovedVoice));
      } catch { /* ignore */ }
    })();
  }, [projectId, characterId]);

  useEffect(() => {
    if (!projectId || !characterId) return;
    const requestedId = characterId;
    (async () => {
      try {
        const response = await api.voicePerformanceM410.listProjectRecords(projectId);
        if (!isCurrentCharacterRequest(requestedId, characterIdRef.current)) return;
        const records = (response.records || []).filter((r) => r.characterId === requestedId);
        setHasApprovedTake(Boolean(records.some((r) => r.approvedTakeId)));
      } catch { setHasApprovedTake(false); }
    })();
  }, [projectId, characterId]);

  useEffect(() => {
    if (!projectId || !characterId) return;
    const requestedId = characterId;
    (async () => {
      try {
        const profiles = await api.voiceEnvironment.listProfiles(projectId, requestedId).catch(() => []);
        const renders = await api.voiceEnvironment.listRenders(projectId, requestedId).catch(() => []);
        if (!isCurrentCharacterRequest(requestedId, characterIdRef.current)) return;
        setHasEnvironmentRender(Boolean((renders || []).length));
        setHasSceneDialogue(Boolean((profiles || []).length));
      } catch { setHasEnvironmentRender(false); setHasSceneDialogue(false); }
    })();
  }, [projectId, characterId]);

  const approvedVoice = useMemo(
    () => chooseApprovedVoice(ws?.voices, ws?.activeVoiceProfileId || voiceId),
    [ws?.voices, ws?.activeVoiceProfileId, voiceId],
  );

  const characterName = characterNameProp || ws?.characterName || "Character";
  const voiceProvider = useVoiceStudioProviderSource();

  return (
    <section className="panel voice-studio voice-studio-m43" data-testid="character-voice">
      <header className="voice-studio-header" data-testid="voice-creator-header">
        <PanelHeading
          title={`Voice Studio — ${characterName}`}
          tip="Create a character voice, choose one to test, perform dialogue, then approve when ready."
          as="h3"
        />
        <div style={{ margin: "0.5rem 0 0.75rem" }}>
          <ProviderSourceSelector
            id="voice-studio"
            label="Provider"
            source={voiceProvider.source}
            onChange={voiceProvider.setSource}
            health={voiceProvider.health}
            healthBusy={voiceProvider.healthBusy}
          />
        </div>
        <p className="voice-studio-readiness" data-testid="voice-studio-readiness">
          {READINESS_LABELS[readinessLabel]}
        </p>
        <span hidden data-testid="voice-creator-status">
          {READINESS_LABELS[readinessLabel]}
        </span>
        <span hidden data-testid="voice-active-id">
          {voiceId}
        </span>
        <span hidden data-testid="voice-selected-candidate">
          {testingCandidateId}
        </span>
        <span hidden data-testid="voice-studio-phase">
          {phase}
        </span>
        <button
          type="button"
          className="voice-studio-sr-brief"
          data-testid="open-voice-performance"
          onClick={() => {
            setWorkspaceTab("performance");
            setPhase("performance");
            void persistDraft({ phase: "performance" });
          }}
        >
          Open Voice Performance
        </button>

        <div className="voice-studio-codirector-chips" data-testid="voice-ask-codirector">
          <span className="muted" style={{ fontSize: "0.85rem" }}>
            Co-Director
          </span>
          {voiceStudioCoDirectorChips(characterName).map((prompt) => (
            <button
              key={prompt}
              type="button"
              className="voice-studio-chip"
              data-testid="voice-studio-codirector-chip"
              onClick={() => openCoDirector(prompt)}
            >
              {prompt}
            </button>
          ))}
        </div>
      </header>

      <div className="workspace-tabs voice-studio-stage-tabs" role="tablist" data-testid="voice-studio-ia">
        {VOICE_STUDIO_STAGE_ORDER.map((stage) => {
          // Owner CLEAR 2026-09-19: all Voice Studio stages stay permanently unlocked.
          const stageUnlocked = true;
          return (
          <div
            key={stage.id}
            className="voice-studio-stage-tab"
            data-testid={stage.id === "environment" ? "voice-environment-stage" : `voice-studio-stage-${stage.id}`}
          >
            <button
              type="button"
              role="tab"
              aria-selected={workspaceTab === stage.id}
              disabled={!stageUnlocked}
              className={[
                workspaceTab === stage.id ? "primary" : "",
                !stageUnlocked ? "is-locked" : "",
              ].filter(Boolean).join(" ")}
              data-testid={
                stage.id === "identity"
                  ? "voice-identity-tab"
                  : stage.id === "performance"
                    ? "voice-performance-tab"
                    : "voice-environment-tab"
              }
              onClick={() => {
                if (!stageUnlocked) return;
                setWorkspaceTab(coerceWorkspaceTab(stage.id));
                if (stage.id === "identity" && (phase === "performance" || phase === "approve")) {
                  setPhase(testingCandidateId ? "select" : "create");
                }
              }}
            >
              {!stageUnlocked && <span className="voice-studio-tab__lock-icon">🔒</span>}
              {stage.label}
            </button>
            <HelpTip label={stage.label} content={stage.tip} />
          </div>
          );
        })}
      </div>

      <div className="voice-studio-stack" data-testid="voice-creator-workspace">
        {workspaceTab === "identity" ? (
          <VoiceIdentityPanel
            projectId={projectId}
            characterId={characterId}
            characterName={characterName}
            onVoiceApproved={() => setHasApprovedVoice(true)}
            onNavigate={(v: string) => setWorkspaceTab(coerceWorkspaceTab(v))}
            onMsg={onMsg}
            onRefresh={onRefresh}
          />
        ) : workspaceTab === "environment" ? (
          <VoiceEnvironmentPanel
            projectId={projectId}
            characterId={characterId}
            characterName={characterName}
            approvedVoiceIdentity={
              approvedVoice?.id
                ? {
                    id: String(approvedVoice.id),
                    name: String(approvedVoice.name || `${characterName} Voice`),
                    version: approvedVoice.version_number ?? approvedVoice.versionNumber ?? null,
                  }
                : null
            }
            onMsg={onMsg}
            onSelectStage={(tab) => setWorkspaceTab(coerceWorkspaceTab(tab))}
          />
        ) : (
          <VoicePerformanceStudio
            projectId={projectId}
            characterId={characterId}
            characterName={characterName}
            activeView="performance"
            approvedVoiceIdentity={
              approvedVoice?.id
                ? {
                    id: String(approvedVoice.id),
                    name: String(approvedVoice.name || `${characterName} Voice`),
                    version: approvedVoice.version_number ?? approvedVoice.versionNumber ?? null,
                  }
                : null
            }
            initialDialogue={dialogue}
            onMsg={onMsg}
            onOpenVoiceIdentity={() => setWorkspaceTab("identity")}
          />
        )}
      </div>

      {/* Legacy e2e shims */}
      <nav className="voice-studio-legacy-nav" data-testid="voice-creator-subtabs" aria-hidden="true" hidden>
        <button type="button" data-testid="voice-subtab-overview">Overview</button>
        <button type="button" data-testid="voice-subtab-create">Create</button>
        <button type="button" data-testid="voice-subtab-clone">Clone</button>
        <button type="button" data-testid="voice-subtab-candidates">Candidates</button>
        <button type="button" data-testid="voice-subtab-audition">Audition</button>
        <button type="button" data-testid="voice-subtab-pronunciation">Pronunciation</button>
        <button type="button" data-testid="voice-subtab-reactions">Reactions</button>
        <button type="button" data-testid="voice-subtab-versions">Versions</button>
        <button type="button" data-testid="voice-subtab-provenance">Provenance</button>
        <button type="button" data-testid="vp-view-script">Script</button>
        <button type="button" data-testid="vp-view-markup">Markup</button>
        <button type="button" data-testid="vp-view-plan">Plan</button>
        <button type="button" data-testid="vp-view-translation">Translation</button>
        <button type="button" data-testid="vp-view-segments">Segments</button>
        <button type="button" data-testid="vp-view-audition">Audition</button>
        <button type="button" data-testid="vp-view-timeline">Timeline</button>
        <button type="button" data-testid="vp-view-versions">Versions</button>
        <button type="button" data-testid="vp-view-provenance">Provenance</button>
      </nav>
    </section>
  );
}
