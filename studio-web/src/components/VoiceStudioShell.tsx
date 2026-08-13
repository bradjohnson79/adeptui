import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { VoicePerformanceRecord } from "../contracts/voicePerformanceM410";
import type { Project } from "../types";
import { PanelHeading } from "./HelpTip";
import { Button } from "./ui";
import { VoiceStudioWorkspace } from "./VoiceStudioWorkspace";

const SELECTED_CHARACTER_KEY = "adept_selected_character";
const PORTRAIT_ROLE_PRIORITY = [
  "hero_identity",
  "hero_portrait",
  "neutral_portrait",
  "closeup_front",
  "full_body_front",
] as const;

type VoiceStudioShellProps = {
  project: Project;
  onChange?: () => void | Promise<void>;
  initialCharacterId?: string;
  returnWorkspace?: string;
};

type CharacterVoiceCard = {
  id: string;
  name: string;
  status: string;
  voiceIdentityState: string;
  approvedVoiceName?: string;
  takeCount?: number;
  portraitAssetId?: string;
};

function chooseApprovedVoice(voices: any[] | undefined): any | null {
  const list = Array.isArray(voices) ? voices : [];
  const approved = [...list]
    .filter((voice) => String(voice?.approval_status || "").toLowerCase() === "approved")
    .sort((a, b) =>
      String(b?.approved_at || b?.updated_at || "").localeCompare(String(a?.approved_at || a?.updated_at || "")),
    );
  return approved[0] || null;
}

function choosePortraitAssetId(refs: any[] | undefined): string | undefined {
  const list = Array.isArray(refs) ? refs : [];
  for (const role of PORTRAIT_ROLE_PRIORITY) {
    const match = list.find((item) => String(item?.reference_role || "") === role && item?.asset_id);
    if (match?.asset_id) return String(match.asset_id);
  }
  return undefined;
}

function pickPreferredRecord(records: VoicePerformanceRecord[], characterId: string) {
  const matching = records
    .filter((record) => record.characterId === characterId)
    .sort((a, b) => String(b.updatedAt || "").localeCompare(String(a.updatedAt || "")));
  return matching.find((record) => record.approvedTakeId) || matching[0] || null;
}

function summarizeVoiceIdentityState(workspace: any, approvedVoice: any | null) {
  if (approvedVoice?.id) return "Approved voice identity";
  if (workspace?.candidateBatches?.length) return "Voice ideas ready to review";
  if (workspace?.voices?.length) return "Voice draft in progress";
  return "Voice identity not started";
}

function persistSelectedCharacter(characterId: string) {
  try {
    sessionStorage.setItem(SELECTED_CHARACTER_KEY, characterId);
    window.dispatchEvent(new CustomEvent("adept:selected-character", { detail: { characterId } }));
  } catch {
    /* ignore */
  }
}

function readRememberedCharacter(): string {
  try {
    return sessionStorage.getItem(SELECTED_CHARACTER_KEY) || "";
  } catch {
    return "";
  }
}

export function VoiceStudioShell({
  project,
  onChange,
  initialCharacterId,
  returnWorkspace,
}: VoiceStudioShellProps) {
  const navigate = useNavigate();
  const [cards, setCards] = useState<CharacterVoiceCard[]>([]);
  const [selectedCharacterId, setSelectedCharacterId] = useState("");
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setMessage("");
    try {
      const [profilesResponse, recordsResponse] = await Promise.all([
        api.listCharacterProfiles(project.id),
        api.voicePerformanceM410.listProjectRecords(project.id).catch(() => ({
          projectId: project.id,
          records: [],
          mock: false,
        })),
      ]);
      const profiles = profilesResponse.items || [];
      const records = recordsResponse.records || [];
      const nextCards = await Promise.all(
        profiles.map(async (profile) => {
          const [refsResponse, voiceWorkspace] = await Promise.all([
            api.listCharacterReferences(project.id, profile.id).catch(() => ({ items: [] })),
            api.getCharacterVoiceWorkspace(project.id, profile.id).catch(() => null),
          ]);
          const approvedVoice = chooseApprovedVoice(voiceWorkspace?.voices);
          const preferredRecord = pickPreferredRecord(records, profile.id);
          const takeCount = preferredRecord?.takes?.length;
          return {
            id: String(profile.id),
            name: String(profile.name || "Untitled Character"),
            status: String(profile.status || "draft"),
            voiceIdentityState: summarizeVoiceIdentityState(voiceWorkspace, approvedVoice),
            approvedVoiceName: approvedVoice?.name ? String(approvedVoice.name) : undefined,
            takeCount: typeof takeCount === "number" && takeCount > 0 ? takeCount : undefined,
            portraitAssetId: choosePortraitAssetId(refsResponse.items),
          } satisfies CharacterVoiceCard;
        }),
      );
      setCards(nextCards);
    } catch (error: any) {
      setMessage(error?.message || "Voice Studio could not load your characters.");
      setCards([]);
    } finally {
      setLoading(false);
    }
  }, [project.id]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!cards.length) return;
    const preferred = initialCharacterId || readRememberedCharacter();
    if (preferred && cards.some((card) => card.id === preferred)) {
      setSelectedCharacterId((current) => current || preferred);
      return;
    }
    if (selectedCharacterId && cards.some((card) => card.id === selectedCharacterId)) return;
    setSelectedCharacterId("");
  }, [cards, initialCharacterId, selectedCharacterId]);

  useEffect(() => {
    if (!selectedCharacterId) return;
    persistSelectedCharacter(selectedCharacterId);
  }, [selectedCharacterId]);

  const selectedCharacter = useMemo(
    () => cards.find((card) => card.id === selectedCharacterId) || null,
    [cards, selectedCharacterId],
  );

  const openCreateCharacter = useCallback(() => {
    navigate({
      pathname: `/project/${project.id}`,
      search: "?workspace=characters&returnWorkspace=voicestudio",
    });
  }, [navigate, project.id]);

  const backToCoDirector = useCallback(() => {
    window.location.assign(`/project/${project.id}?workspace=codirector`);
  }, [project.id]);

  if (selectedCharacter) {
    return (
      <section className="page voice-studio-shell" data-testid="voice-studio-shell">
        <div className="voice-studio-shell__active">
          <div className="voice-studio-shell__active-summary">
            <div>
              <PanelHeading
                title={`Voice Studio — ${selectedCharacter.name}`}
                tip="Choose a character, shape the voice identity, direct performances, build the scene acoustic, and approve the take you want to keep."
              />
              <p className="scene-meta">
                {selectedCharacter.voiceIdentityState}
                {selectedCharacter.approvedVoiceName ? ` · Approved voice: ${selectedCharacter.approvedVoiceName}` : ""}
                {selectedCharacter.takeCount ? ` · ${selectedCharacter.takeCount} take${selectedCharacter.takeCount === 1 ? "" : "s"}` : ""}
              </p>
            </div>
            <div className="voice-studio-actions">
              {returnWorkspace === "codirector" ? (
                <Button
                  type="button"
                  data-testid="voicestudio-back-to-codirector"
                  onClick={backToCoDirector}
                >
                  ← Back to Co-Director
                </Button>
              ) : null}
              <Button type="button" onClick={() => setSelectedCharacterId("")}>
                Choose Another Character
              </Button>
              <Button type="button" onClick={openCreateCharacter}>
                Create New Character
              </Button>
            </div>
          </div>
          {message ? <p className="pill">{message}</p> : null}
          <VoiceStudioWorkspace
            projectId={project.id}
            characterId={selectedCharacter.id}
            onMsg={setMessage}
            onRefresh={() => {
              void load();
              void onChange?.();
            }}
          />
        </div>
      </section>
    );
  }

  return (
    <section className="page voice-studio-shell" data-testid="voice-studio-shell">
      <div className="voice-performance-studio__dialogue voice-studio-shell__chooser">
        <PanelHeading
          title="Voice Studio"
          tip="Pick a character to build their voice identity, direct dialogue performances, and shape how the line lives inside the scene."
        />
        <p className="muted">
          Start with a character, then shape the voice, direct the performance, build the scene acoustic, and approve the take you want to carry forward.
        </p>
        {message ? (
          <p className="pill" data-testid="voice-studio-shell-message">
            {message}
          </p>
        ) : null}
        <div className="voice-studio-actions">
          {returnWorkspace === "codirector" ? (
            <Button
              type="button"
              data-testid="voicestudio-back-to-codirector"
              onClick={backToCoDirector}
            >
              ← Back to Co-Director
            </Button>
          ) : null}
          <Button type="button" className="voice-studio-primary-cta" onClick={openCreateCharacter}>
            Create New Character
          </Button>
        </div>
        {loading ? (
          <p className="empty">Loading characters…</p>
        ) : !cards.length ? (
          <div className="voice-performance-studio__identity-gate" data-testid="voice-studio-shell-empty">
            <PanelHeading
              title="Create your first character"
              tip="Voice Studio stays centered on real project characters. Create one first, then come back here."
              as="h3"
            />
            <p className="muted">
              Character voices live on Character Profiles so every approved voice, performance, and take stays tied to the open project.
            </p>
            <Button type="button" variant="primary" className="voice-studio-primary-cta" onClick={openCreateCharacter}>
              Create New Character
            </Button>
          </div>
        ) : (
          <div className="voice-studio-gallery" data-testid="voice-studio-shell-grid">
            {cards.map((card) => (
              <article key={card.id} className="voice-studio-candidate-card voice-studio-shell__card">
                <div className="voice-studio-shell__portrait">
                  {card.portraitAssetId ? (
                    <img src={api.assetUrl(card.portraitAssetId)} alt={card.name} />
                  ) : (
                    <div className="voice-studio-shell__portrait-fallback">{card.name.slice(0, 1).toUpperCase()}</div>
                  )}
                </div>
                <div className="voice-studio-shell__card-body">
                  <div>
                    <strong>{card.name}</strong>
                    <p className="muted">{card.status.replace(/_/g, " ")}</p>
                  </div>
                  <dl className="voice-studio-shell__facts">
                    <div>
                      <dt>Voice Identity</dt>
                      <dd>{card.voiceIdentityState}</dd>
                    </div>
                    <div>
                      <dt>Approved Voice</dt>
                      <dd>{card.approvedVoiceName || "Not approved yet"}</dd>
                    </div>
                    {card.takeCount ? (
                      <div>
                        <dt>Takes</dt>
                        <dd>{card.takeCount}</dd>
                      </div>
                    ) : null}
                  </dl>
                  <Button
                    type="button"
                    variant="primary"
                    className="voice-studio-primary-cta"
                    onClick={() => setSelectedCharacterId(card.id)}
                  >
                    Open Voice Studio
                  </Button>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
