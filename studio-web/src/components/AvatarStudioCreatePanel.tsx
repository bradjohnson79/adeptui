import { LoRASelector } from "./lora/LoRASelector";
import { CharacterReferenceAssetPicker } from "./CoDirector/characters/CharacterReferenceAssetPicker";
import {
  AVATAR_ASPECT_RATIOS,
  AVATAR_BACKGROUND_OPTIONS,
  AVATAR_DURATION_OPTIONS,
  AVATAR_FRAMING_OPTIONS,
  AVATAR_GENERATOR_IDS,
  AVATAR_STYLE_OPTIONS,
  loraFamilyForGenerator,
  speakerLabel,
  type AvatarRuntimeCapabilities,
  type AvatarSourceKind,
} from "../avatar/compact";
import type { AvatarRuntimeGate, AvatarSession } from "../avatar/types";
import type { SetupComponentStatus } from "../setup/types";

type ProfileItem = {
  id: string;
  name: string;
  stillAssetId?: string | null;
};

type AssetItem = {
  id: string;
  tag?: string;
  filename?: string;
};

type ApprovedVoiceChoice = {
  recordId: string;
  takeId: string;
  audioAssetId: string;
  voiceIdentityId: string;
  providerId: string;
  title: string;
  subtitle: string;
  updatedAt: string;
};

function Tip({ text }: { text: string }) {
  return (
    <span className="avatar-inline-tip" title={text} aria-label={text}>
      {" "}
      (?)
    </span>
  );
}

function displayTime(value?: string | null): string {
  if (!value) return "Just now";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Just now";
  return parsed.toLocaleString();
}

export function AvatarStudioCreatePanel({
  projectId,
  session,
  patchSession,
  characters,
  characterStills,
  imageAssets,
  videoAssets,
  audioAssets,
  approvedVoices,
  voiceReadiness,
  runtimeComponents,
  capabilities,
  selectedProvider,
  selectedRuntimeGate,
  generateBlockReason,
  canGenerate,
  busy,
  backgroundPickerOpen,
  setBackgroundPickerOpen,
  sourcePickerOpen,
  setSourcePickerOpen,
  speakerOverlayActive,
  setSpeakerOverlayActive,
  onBindCharacter,
  onGenerate,
  onOpenSetup,
  onGoVoice,
  onDetectSpeakers,
  onAskPlan,
  onCreatePlan,
}: {
  projectId: string;
  session: AvatarSession;
  patchSession: (patch: Partial<AvatarSession>) => void;
  characters: ProfileItem[];
  characterStills: Record<string, string>;
  imageAssets: AssetItem[];
  videoAssets: AssetItem[];
  audioAssets: AssetItem[];
  approvedVoices: ApprovedVoiceChoice[];
  voiceReadiness: { approvedVoice?: boolean } | null;
  runtimeComponents: SetupComponentStatus[];
  capabilities: AvatarRuntimeCapabilities[];
  selectedProvider: SetupComponentStatus | null;
  selectedRuntimeGate: AvatarRuntimeGate;
  generateBlockReason: string;
  canGenerate: boolean;
  busy: boolean;
  backgroundPickerOpen: boolean;
  setBackgroundPickerOpen: (open: boolean) => void;
  sourcePickerOpen: boolean;
  setSourcePickerOpen: (open: boolean) => void;
  speakerOverlayActive: boolean;
  setSpeakerOverlayActive: (open: boolean) => void;
  onBindCharacter: (characterId: string) => void;
  onGenerate: () => void;
  onOpenSetup: (componentId?: string) => void;
  onGoVoice: () => void;
  onDetectSpeakers: () => void;
  onAskPlan: () => void;
  onCreatePlan: () => void;
}) {
  const sourceKind: AvatarSourceKind = session.source_kind || "character";
  const speakers = session.speakers?.length
    ? session.speakers
    : [{ id: "speaker-a", label: "Person 1", character_id: session.character_profile_id || null }];
  const speakerA = speakers.find((item) => item.id === "speaker-a") || speakers[0];
  const speakerB = speakers.find((item) => item.id === "speaker-b") || speakers[1];
  const canConversation = speakers.length >= 2 || Boolean(speakerA && speakerB);
  const modeKind = session.mode_kind === "conversation" && canConversation ? "conversation" : "single";
  const conversation = session.conversation || { order: "a_then_b" as const, turns: [] };
  const turnFor = (speakerId: string) =>
    conversation.turns.find((turn) => turn.speakerId === speakerId)?.dialogue || "";
  const generatorId =
    session.provider_choice ||
    session.model_id ||
    selectedProvider?.id ||
    "infinitetalk-local";
  const selectedCaps =
    capabilities.find((item) => item.id === generatorId) ||
    capabilities.find((item) => item.listedAsAvatarGenerator) ||
    null;
  const aspectOptions = (selectedCaps?.supportedAspectRatios || [...AVATAR_ASPECT_RATIOS]).filter((ratio) =>
    (AVATAR_ASPECT_RATIOS as readonly string[]).includes(ratio),
  );
  const currentAspect = session.look?.aspect || session.camera?.aspect || "16:9";
  const listedGenerators = runtimeComponents.filter((item) =>
    (AVATAR_GENERATOR_IDS as readonly string[]).includes(item.id),
  );
  const voiceMode =
    session.input_mode === "approved_voice" ? "approved" : session.voice?.audio_asset_id ? "file" : "none";

  const setTurn = (speakerId: string, dialogue: string) => {
    const otherId = speakerId === "speaker-a" ? "speaker-b" : "speaker-a";
    const other = conversation.turns.find((turn) => turn.speakerId === otherId);
    const nextTurns =
      modeKind === "conversation"
        ? [
            { speakerId: "speaker-a", dialogue: speakerId === "speaker-a" ? dialogue : turnFor("speaker-a") },
            { speakerId: "speaker-b", dialogue: speakerId === "speaker-b" ? dialogue : other?.dialogue || "" },
          ]
        : [{ speakerId: "speaker-a", dialogue }];
    patchSession({
      dialogue_original: modeKind === "conversation" ? nextTurns.map((turn) => turn.dialogue).filter(Boolean).join("\n\n") : dialogue,
      conversation: { ...conversation, turns: nextTurns },
    });
  };

  const assignSpeakerCharacter = (speakerId: string, characterId: string) => {
    const character = characters.find((item) => item.id === characterId);
    const next = speakers.map((item) =>
      item.id === speakerId
        ? {
            ...item,
            character_id: characterId || null,
            label: character?.name || (speakerId === "speaker-a" ? "Person 1" : "Person 2"),
          }
        : item,
    );
    const patch: Partial<AvatarSession> = { speakers: next };
    if (speakerId === "speaker-a" && characterId) {
      patch.character_profile_id = characterId;
      patch.character_name = character?.name || session.character_name;
      if (character?.stillAssetId || characterStills[characterId]) {
        patch.source_still_asset_id = character?.stillAssetId || characterStills[characterId] || null;
      }
    }
    patchSession(patch);
    if (speakerId === "speaker-a" && characterId) onBindCharacter(characterId);
  };

  return (
    <aside className="dash-card avatar-create-panel" data-testid="avatar-create-panel">
      <div className="avatar-create-panel__heading">
        <div>
          <p className="eyebrow">Create</p>
          <h2>Avatar Video</h2>
        </div>
      </div>

      <section className="avatar-create-section">
        <div className="avatar-section-title-row">
          <h3>Source</h3>
          <Tip text="Choose who or what should appear. Character uses this project's people. Library Image and Existing Still use a picture you already have." />
        </div>
        <select
          data-testid="avatar-source-kind"
          value={sourceKind}
          onChange={(event) => {
            const next = event.target.value as AvatarSourceKind;
            patchSession({
              source_kind: next,
              mode: next === "video" ? "existing_video_lipsync" : session.mode === "existing_video_lipsync" ? "talking_portrait" : session.mode,
            });
          }}
        >
          <option value="character">Character</option>
          <option value="library">Library Image</option>
          <option value="still">Existing Still</option>
          <option value="video">Existing Video</option>
        </select>
        {sourceKind === "character" ? (
          <div className="field" style={{ marginTop: "0.65rem" }}>
            <label>Character</label>
            <select
              data-testid="avatar-character-select"
              value={session.character_profile_id || ""}
              onChange={(event) => {
                const nextId = event.target.value;
                if (!nextId) {
                  patchSession({ character_profile_id: null, character_name: "" });
                  return;
                }
                onBindCharacter(nextId);
              }}
            >
              <option value="">Select character…</option>
              {characters.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            {!session.character_profile_id ? (
              <p className="scene-meta" data-testid="avatar-requires-character">
                Pick a character from this project, or switch Source to Library Image.
              </p>
            ) : null}
          </div>
        ) : null}
        {sourceKind === "library" || sourceKind === "still" ? (
          <div className="avatar-inline-actions" style={{ marginTop: "0.65rem" }}>
            <button type="button" onClick={() => setSourcePickerOpen(true)}>
              {session.source_still_asset_id ? "Change image" : "Pick image"}
            </button>
            <select
              data-testid="avatar-source-still"
              value={session.source_still_asset_id || ""}
              onChange={(event) => patchSession({ source_still_asset_id: event.target.value || null })}
            >
              <option value="">Select still…</option>
              {imageAssets.map((asset) => (
                <option key={asset.id} value={asset.id}>
                  {asset.tag || asset.filename}
                </option>
              ))}
            </select>
          </div>
        ) : null}
        {sourceKind === "video" ? (
          <div className="field" style={{ marginTop: "0.65rem" }}>
            <label>Existing Video</label>
            <select
              data-testid="avatar-source-video"
              value={session.source_video_asset_id || ""}
              onChange={(event) => patchSession({ source_video_asset_id: event.target.value || null })}
            >
              <option value="">Select video…</option>
              {videoAssets.map((asset) => (
                <option key={asset.id} value={asset.id}>
                  {asset.tag || asset.filename}
                </option>
              ))}
            </select>
          </div>
        ) : null}
        <CharacterReferenceAssetPicker
          projectId={projectId}
          currentAssetId={session.source_still_asset_id}
          open={sourcePickerOpen}
          onCancel={() => setSourcePickerOpen(false)}
          onConfirm={(asset) => {
            patchSession({
              source_kind: sourceKind === "still" ? "still" : "library",
              source_still_asset_id: asset.id,
            });
            setSourcePickerOpen(false);
          }}
        />
      </section>

      <section className="avatar-create-section">
        <div className="avatar-section-title-row">
          <h3>Speaker</h3>
          <Tip text="Conversation is available when two people are in the picture, or when you assign Speaker A and Speaker B. Names only appear after you assign them." />
        </div>
        <select
          data-testid="avatar-mode-kind"
          value={modeKind}
          onChange={(event) => {
            const next = event.target.value === "conversation" ? "conversation" : "single";
            if (next === "conversation" && speakers.length < 2) {
              patchSession({
                mode_kind: "conversation",
                speakers: [
                  speakerA,
                  {
                    id: "speaker-b",
                    label: "Person 2",
                    character_id: null,
                    bbox: null,
                    mask_asset_id: null,
                  },
                ],
                conversation: {
                  order: conversation.order || "a_then_b",
                  turns: [
                    { speakerId: "speaker-a", dialogue: turnFor("speaker-a") || session.dialogue_original || "" },
                    { speakerId: "speaker-b", dialogue: turnFor("speaker-b") },
                  ],
                },
              });
              return;
            }
            patchSession({ mode_kind: next });
          }}
        >
          <option value="single">Single Speaker</option>
          <option value="conversation">Conversation</option>
        </select>
        <div className="avatar-inline-actions" style={{ marginTop: "0.55rem" }}>
          <button type="button" onClick={onDetectSpeakers} disabled={busy || !session.source_still_asset_id}>
            Find people in picture
          </button>
          <button
            type="button"
            className={speakerOverlayActive ? "primary" : ""}
            onClick={() => setSpeakerOverlayActive(!speakerOverlayActive)}
            disabled={!speakers.some((item) => item.bbox)}
          >
            Select Speaker Region
          </button>
        </div>
        <div className="field" style={{ marginTop: "0.55rem" }}>
          <label>{modeKind === "conversation" ? "Speaker A" : "Speaker"}</label>
          <select
            data-testid="avatar-speaker-a"
            value={speakerA?.character_id || "person-1"}
            onChange={(event) => assignSpeakerCharacter("speaker-a", event.target.value === "person-1" ? "" : event.target.value)}
          >
            <option value="person-1">Person 1</option>
            {characters.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
        {modeKind === "conversation" ? (
          <>
            <div className="field">
              <label>Speaker B</label>
              <select
                data-testid="avatar-speaker-b"
                value={speakerB?.character_id || "person-2"}
                onChange={(event) => assignSpeakerCharacter("speaker-b", event.target.value === "person-2" ? "" : event.target.value)}
              >
                <option value="person-2">Person 2</option>
                {characters.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Speaking order</label>
              <select
                data-testid="avatar-conversation-order"
                value={conversation.order || "a_then_b"}
                onChange={(event) =>
                  patchSession({
                    conversation: {
                      ...conversation,
                      order: event.target.value === "b_then_a" ? "b_then_a" : "a_then_b",
                    },
                  })
                }
              >
                <option value="a_then_b">A then B</option>
                <option value="b_then_a">B then A</option>
              </select>
            </div>
          </>
        ) : null}
        {selectedCaps && !selectedCaps.supportsNativeMultiSpeaker && modeKind === "conversation" ? (
          <p className="scene-meta" data-testid="avatar-conversation-limit">
            This generator cannot film two people talking at the same time. Conversation is made as Speaker A,
            then Speaker B, then joined together.
          </p>
        ) : null}
      </section>

      <section className="avatar-create-section">
        <div className="avatar-section-title-row">
          <h3>Dialogue</h3>
          <Tip text="Write the words each speaker should say. Conversation keeps each person's lines separate." />
        </div>
        {modeKind === "conversation" ? (
          <>
            <div className="field">
              <label>{speakerLabel(speakerA, 1)} lines</label>
              <textarea
                data-testid="avatar-dialogue-a"
                rows={3}
                value={turnFor("speaker-a")}
                onChange={(event) => setTurn("speaker-a", event.target.value)}
                placeholder="What Speaker A says."
              />
            </div>
            <div className="field">
              <label>{speakerLabel(speakerB, 2)} lines</label>
              <textarea
                data-testid="avatar-dialogue-b"
                rows={3}
                value={turnFor("speaker-b")}
                onChange={(event) => setTurn("speaker-b", event.target.value)}
                placeholder="What Speaker B says."
              />
            </div>
          </>
        ) : (
          <div className="field">
            <label>Lines</label>
            <textarea
              data-testid="avatar-dialogue"
              rows={4}
              value={session.dialogue_original}
              onChange={(event) => setTurn("speaker-a", event.target.value)}
              placeholder="Write the words the speaker should say."
            />
          </div>
        )}
        <div className="field">
          <label>
            Voice
            <Tip text="Approved uses a finished Voice Studio take. Audio file uses a clip from the Library. None plans the picture without lip-sync audio." />
          </label>
          <select
            data-testid="avatar-voice-mode"
            value={voiceMode}
            onChange={(event) => {
              const next = event.target.value;
              if (next === "approved") {
                patchSession({ input_mode: "approved_voice" });
                return;
              }
              patchSession({
                input_mode: "script",
                voice:
                  next === "none"
                    ? { ...session.voice, audio_asset_id: null, fallback_audio_asset_id: null }
                    : session.voice,
              });
            }}
          >
            <option value="none">None</option>
            <option value="approved">Approved</option>
            <option value="file">Audio file</option>
          </select>
        </div>
        {session.input_mode === "approved_voice" ? (
          approvedVoices.length ? (
            <select
              data-testid="avatar-approved-voice"
              value={session.voice.approved_take_id || ""}
              onChange={(event) => {
                const item = approvedVoices.find((voice) => voice.takeId === event.target.value);
                if (!item) return;
                patchSession({
                  input_mode: "approved_voice",
                  voice: {
                    ...session.voice,
                    provider: "voice-performance-m410",
                    audio_asset_id: item.audioAssetId,
                    approved_record_id: item.recordId,
                    approved_take_id: item.takeId,
                    profile_id: item.voiceIdentityId,
                    model: item.providerId,
                  },
                  links: {
                    ...session.links,
                    voice_record_id: item.recordId,
                    voice_take_id: item.takeId,
                  },
                });
              }}
            >
              <option value="">Select approved take…</option>
              {approvedVoices.map((item) => (
                <option key={item.takeId} value={item.takeId}>
                  {item.title} · {displayTime(item.updatedAt)}
                </option>
              ))}
            </select>
          ) : (
            <div className="avatar-inline-actions">
              <span className="scene-meta">
                {voiceReadiness?.approvedVoice
                  ? "No approved take is attached yet."
                  : "Approve a take in Voice Studio first."}
              </span>
              <button type="button" onClick={onGoVoice}>
                Open Voice Studio
              </button>
            </div>
          )
        ) : null}
        {voiceMode === "file" ? (
          <select
            data-testid="avatar-audio-file"
            value={session.voice.audio_asset_id || session.voice.fallback_audio_asset_id || ""}
            onChange={(event) =>
              patchSession({
                voice: { ...session.voice, audio_asset_id: event.target.value || null, fallback_audio_asset_id: event.target.value || null },
              })
            }
          >
            <option value="">Select audio file…</option>
            {audioAssets.map((asset) => (
              <option key={asset.id} value={asset.id}>
                {asset.tag || asset.filename}
              </option>
            ))}
          </select>
        ) : null}
      </section>

      <section className="avatar-create-section">
        <div className="avatar-section-title-row">
          <h3>Generator</h3>
          <Tip text="Only talking-head generators appear here. Generic video models are not listed as avatar tools." />
        </div>
        <select
          data-testid="avatar-generator"
          value={generatorId}
          onChange={(event) =>
            patchSession({
              provider_mode: "choose_provider",
              provider_choice: event.target.value,
              model_id: event.target.value,
            })
          }
        >
          {listedGenerators.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
        <p className="scene-meta" data-testid="avatar-runtime-gate">
          {generateBlockReason || `${selectedRuntimeGate.name || "InfiniteTalk"} needs repair — Open Runtime Setup`}
        </p>
      </section>

      <section className="avatar-create-section">
        <div className="avatar-section-title-row">
          <h3>Aspect ratio</h3>
          <Tip text="Pick the frame shape. Square, portrait, and widescreen are available when this generator supports them." />
        </div>
        <select
          data-testid="avatar-aspect"
          value={aspectOptions.includes(currentAspect) ? currentAspect : aspectOptions[0] || "16:9"}
          onChange={(event) =>
            patchSession({
              look: { ...session.look, aspect: event.target.value },
              camera: { ...session.camera, aspect: event.target.value },
            })
          }
        >
          {aspectOptions.map((ratio) => (
            <option key={ratio} value={ratio}>
              {ratio}
            </option>
          ))}
        </select>
      </section>

      <div className="avatar-create-panel__cta">
        <button
          type="button"
          className="primary avatar-generate-button"
          data-testid="avatar-generate-button"
          onClick={onGenerate}
          disabled={busy || !canGenerate}
          aria-disabled={busy || !canGenerate}
          title={!canGenerate ? generateBlockReason : "Plan sections. Live talking-head video is not certified yet."}
        >
          {busy ? "Working..." : "Generate Avatar Video"}
        </button>
        <p className="muted" data-testid="avatar-generate-reason">
          {canGenerate
            ? "Creates a section plan. Live talking-head video is not certified in this pass."
            : generateBlockReason}
        </p>
        {!canGenerate && generateBlockReason.includes("Runtime Setup") ? (
          <button type="button" onClick={() => onOpenSetup(selectedProvider?.id)}>
            Open Runtime Setup
          </button>
        ) : null}
      </div>

      <details className="avatar-advanced-panel" data-testid="avatar-advanced-panel">
        <summary data-testid="avatar-advanced-toggle">
          Advanced
          <Tip text="Optional look, timing, and technical notes. The main steps above are enough to generate." />
        </summary>
        <div className="avatar-advanced-panel__body">
          <div className="field">
            <label>Presentation style</label>
            <select
              data-testid="avatar-style-select"
              value={session.presentation_style || "direct_presenter"}
              onChange={(event) => patchSession({ presentation_style: event.target.value })}
            >
              {AVATAR_STYLE_OPTIONS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Framing</label>
            <select
              data-testid="avatar-framing-select"
              value={session.framing_choice || "medium_presenter"}
              onChange={(event) => patchSession({ framing_choice: event.target.value })}
            >
              {AVATAR_FRAMING_OPTIONS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Background</label>
            <select
              data-testid="avatar-background-select"
              value={session.background_choice || "studio_gradient"}
              onChange={(event) => patchSession({ background_choice: event.target.value, background_asset_id: null })}
            >
              {AVATAR_BACKGROUND_OPTIONS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
            <button type="button" onClick={() => setBackgroundPickerOpen(true)}>
              {session.background_asset_id ? "Change Library plate" : "Use Library plate"}
            </button>
          </div>
          <div className="field">
            <label>Duration</label>
            <select
              data-testid="avatar-duration-select"
              value={session.duration_class || "story_section"}
              onChange={(event) => patchSession({ duration_class: event.target.value })}
            >
              {AVATAR_DURATION_OPTIONS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Creative notes</label>
            <textarea
              data-testid="avatar-direction-prompt"
              rows={2}
              value={session.direction_prompt || ""}
              onChange={(event) => patchSession({ direction_prompt: event.target.value })}
              placeholder="How this should feel, without changing the spoken lines."
            />
          </div>
          <div className="field">
            <label>Fallback audio</label>
            <select
              data-testid="avatar-fallback-audio"
              value={session.voice.fallback_audio_asset_id || ""}
              onChange={(event) =>
                patchSession({
                  voice: { ...session.voice, fallback_audio_asset_id: event.target.value || null },
                })
              }
            >
              <option value="">None</option>
              {audioAssets.map((asset) => (
                <option key={asset.id} value={asset.id}>
                  {asset.tag || asset.filename}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Exclude notes</label>
            <textarea
              rows={2}
              value={session.negative_prompt}
              onChange={(event) => patchSession({ negative_prompt: event.target.value })}
              placeholder="What should the avatar avoid?"
            />
          </div>
          <div className="field">
            <label>Presentation plan</label>
            <textarea
              data-testid="avatar-presentation-plan-summary"
              rows={2}
              value={session.presentation_plan?.summary || ""}
              onChange={(event) =>
                patchSession({
                  presentation_plan: {
                    ...(session.presentation_plan as NonNullable<AvatarSession["presentation_plan"]>),
                    summary: event.target.value,
                  },
                })
              }
              placeholder="Optional direction notes for later sectioning."
            />
            <div className="avatar-inline-actions">
              <button type="button" onClick={onAskPlan} disabled={busy}>
                Ask Co-Director to Plan
              </button>
              <button type="button" className="primary" onClick={onCreatePlan} disabled={busy}>
                Create Plan Proposal
              </button>
            </div>
          </div>
          <LoRASelector
            modelFamily={loraFamilyForGenerator(generatorId)}
            modality="video"
            compact
            value={session.lora || null}
            onChange={(lora) => patchSession({ lora })}
          />
          <div className="avatar-inline-actions">
            <button type="button" onClick={() => onOpenSetup(selectedProvider?.id)}>
              Open Runtime Setup
            </button>
          </div>
          <CharacterReferenceAssetPicker
            projectId={projectId}
            currentAssetId={session.background_asset_id}
            open={backgroundPickerOpen}
            onCancel={() => setBackgroundPickerOpen(false)}
            onConfirm={(asset) => {
              patchSession({
                background_choice: "library_plate",
                background_asset_id: asset.id,
                background_mode: "environment",
                background_notes: `Library plate ${asset.tag || asset.filename || asset.id}`,
              });
              setBackgroundPickerOpen(false);
            }}
          />
        </div>
      </details>
    </aside>
  );
}
