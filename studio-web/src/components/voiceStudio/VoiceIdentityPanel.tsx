import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import { Button } from "../ui";
import { PanelHeading } from "../HelpTip";
import "./VoiceIdentityPanel.css";

const AGE_OPTIONS = [
  "Child 5-8", "Child 9-12", "Young Teen 13-15", "Teen 16-19",
  "Young Adult 20-24", "Young Adult 25-29", "Adult 30-34", "Adult 35-39",
  "Adult 40-44", "Adult 45-49", "Mature 50-54", "Mature 55-59",
  "Senior 60-64", "Senior 65-69", "Senior 70-79", "Elder 80+",
] as const;

const ARCHETYPES = [
  "Hero", "Antihero", "Villain", "Mentor", "Leader", "Rebel", "Trickster",
  "Explorer", "Scientist", "Mystic", "Caregiver", "Outsider", "Royal",
  "Warrior", "Scholar", "Detective", "Comedian", "Romantic", "Guardian",
  "Inventor", "Diplomat", "Survivor", "Dreamer", "Commander", "Everyperson",
  "Custom",
] as const;

const ACCENTS = [
  "Neutral American", "General American", "Southern American", "New York",
  "Boston", "Midwestern American", "Canadian", "British RP", "London",
  "Northern English", "Scottish", "Irish", "Welsh", "Australian",
  "New Zealand", "French-accented English", "German-accented English",
  "Italian-accented English", "Spanish-accented English", "Eastern European",
  "Russian-accented English", "Indian English", "South African", "Caribbean",
  "Custom",
] as const;

const SAMPLE_LINES = [
  { id: "greeting", text: "Hey there. Didn't expect to see you here." },
  { id: "question", text: "What makes you think you can just walk in like that?" },
  { id: "serious", text: "Listen carefully, because I'm only going to say this once." },
  { id: "warm", text: "It's good to see you. Really. I mean it." },
  { id: "excited", text: "You have no idea how long I've been waiting for this moment!" },
];

const METHOD_CARDS = [
  {
    id: "create" as const,
    label: "Create New Voice",
    description: "Design a new voice from scratch",
    icon: "\U+1F3A4",
  },
  {
    id: "existing" as const,
    label: "Use Existing Voice",
    description: "Select from saved voice profiles",
    icon: "\U+1F4C1",
  },
  {
    id: "clone" as const,
    label: "Clone from Recording",
    description: "Clone a voice from a recording",
    icon: "\U+1F4CB",
  },
  {
    id: "upload" as const,
    label: "Upload Voice",
    description: "Upload a prepared voice file",
    icon: "\U+1F4E4",
  },
];

type VoiceMethod = "create" | "existing" | "clone" | "upload";

type GeneratedSample = {
  id: string;
  status: string;
  audioUrl?: string;
};

type Props = {
  projectId: string;
  characterId: string;
  characterName?: string;
  onMsg: (m: string) => void;
  onVoiceApproved?: () => void;
  onNavigate?: (tab: string) => void;
  onRefresh?: () => void;
};

export function VoiceIdentityPanel({ projectId, characterId, characterName, onMsg, onVoiceApproved: _onVoiceApproved, onNavigate: _onNavigate, onRefresh: _onRefresh }: Props) {
  const [characters, setCharacters] = useState<any[]>([]);
  const [selectedCharacterId, setSelectedCharacterId] = useState(characterId);
  const [selectedCharacterName, setSelectedCharacterName] = useState(characterName);
  const [creatingCharacter, setCreatingCharacter] = useState(false);
  const [newCharName, setNewCharName] = useState("");

  const [method, setMethod] = useState<VoiceMethod | null>(null);
  const [sex, setSex] = useState<"female" | "male">("female");
  const [age, setAge] = useState<string>(AGE_OPTIONS[4]);
  const [script, setScript] = useState("");
  const [promptDetails, setPromptDetails] = useState("");

  const [emotion, setEmotion] = useState(0);
  const [intensity, setIntensity] = useState(0);
  const [speed, setSpeed] = useState(0);
  const [pitch, setPitch] = useState(0);

  const [archetype, setArchetype] = useState<string>(ARCHETYPES[0]);
  const [accent, setAccent] = useState<string>(ACCENTS[0]);
  const [sampleCount, setSampleCount] = useState<1 | 2 | 3 | 4>(4);

  const [generationState, setGenerationState] = useState<"idle" | "generating" | "done">("idle");
  const [samples, setSamples] = useState<GeneratedSample[]>([]);
  const [approvedVoice, setApprovedVoice] = useState<any | null>(null);
  const [hasApprovedVoice, setHasApprovedVoice] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  const [refineLoading, setRefineLoading] = useState(false);
  const [refinePreview, setRefinePreview] = useState<string | null>(null);

  const loadCharacters = useCallback(async () => {
    try {
      const res = await api.listCharacterProfiles(projectId);
      setCharacters(res.items || []);
    } catch {
      /* ignore */
    }
  }, [projectId]);

  const loadApprovedStatus = useCallback(async () => {
    try {
      const res: any = await api.voiceApprovedStatus(projectId);
      const approved = res?.approvedVoice || res?.items?.[0] || null;
      setApprovedVoice(approved);
      setHasApprovedVoice(Boolean(approved));
    } catch {
      /* ignore */
    }
  }, [projectId]);

  useEffect(() => {
    void loadCharacters();
    void loadApprovedStatus();
  }, [loadCharacters, loadApprovedStatus]);

  const handleCreateCharacter = useCallback(async () => {
    if (!newCharName.trim()) return;
    try {
      const created = await api.createCharacterProfile(projectId, { name: newCharName.trim() });
      const id = created?.id || created?.characterId || created?.item?.id || "";
      if (id) {
        setSelectedCharacterId(id);
        setSelectedCharacterName(newCharName.trim());
        setCreatingCharacter(false);
        setNewCharName("");
        await loadCharacters();
      }
    } catch {
      /* ignore */
    }
  }, [newCharName, projectId, loadCharacters]);

  const handleRefinePrompt = useCallback(async () => {
    if (!promptDetails.trim()) return;
    setRefineLoading(true);
    try {
      const res = await api.codirectorChat({
        messages: [
          {
            role: "user",
            content: "Improve this voice prompt for character \"" + selectedCharacterName + "\":\n\n" + promptDetails,
          },
        ],
        project_id: projectId,
        mode: "prompt",
      });
      if (res?.reply) setRefinePreview(res.reply);
    } catch {
      onMsg("Failed to refine prompt with Co-Director.");
    } finally {
      setRefineLoading(false);
    }
  }, [promptDetails, selectedCharacterName, projectId, onMsg]);

  const handleAcceptRefine = useCallback(() => {
    if (refinePreview) {
      setPromptDetails(refinePreview);
      setRefinePreview(null);
    }
  }, [refinePreview]);

  const handleRejectRefine = useCallback(() => {
    setRefinePreview(null);
  }, []);

  const validate = useCallback((): string[] => {
    const errs: string[] = [];
    if (!selectedCharacterId) errs.push("Please select a character.");
    if (!method) errs.push("Please select a voice method.");
    if (method === "create") {
      if (!sex) errs.push("Please select a voice type.");
      if (!age) errs.push("Please select an age range.");
    }
    return errs;
  }, [selectedCharacterId, method, sex, age]);

  const handleGenerate = useCallback(async () => {
    const errs = validate();
    setErrors(errs);
    if (errs.length > 0) return;

    setGenerationState("generating");
    setSamples([]);
    try {
      const body: Record<string, unknown> = {
        sex,
        age,
        script: script.trim() || undefined,
        prompt: promptDetails.trim() || undefined,
        emotion,
        intensity,
        speed,
        pitch,
        archetype,
        accent,
        sampleCount,
      };
      const res = await api.generateCharacterVoiceCandidates(projectId, selectedCharacterId, body);
      const items: GeneratedSample[] = (res?.candidates || res?.items || []).map((c: any) => ({
        id: c.id,
        status: c.status || "ready",
        audioUrl: c.assetId ? api.assetUrl(c.assetId) : undefined,
      }));
      setSamples(items);
      setGenerationState("done");
    } catch {
      setGenerationState("idle");
      onMsg("Voice generation failed.");
    }
  }, [
    validate, sex, age, script, promptDetails, emotion, intensity, speed, pitch,
    archetype, accent, sampleCount, projectId, selectedCharacterId, onMsg,
  ]);

  const handleApprove = useCallback(
    async (sampleId: string) => {
      try {
        const candidate = samples.find((s) => s.id === sampleId);
        if (!candidate) return;
        await api.approveCharacterVoiceCandidate(projectId, selectedCharacterId, {
          candidateId: sampleId,
        });
        setApprovedVoice({
          id: sampleId,
          name: selectedCharacterName + " Voice",
          characterName: selectedCharacterName,
          audioUrl: candidate.audioUrl,
          approvedAt: new Date().toISOString(),
        });
        setHasApprovedVoice(true);
        onMsg("Voice approved.");
      } catch {
        onMsg("Failed to approve voice candidate.");
      }
    },
    [samples, projectId, selectedCharacterId, selectedCharacterName, onMsg],
  );

  return (
    <section className="voice-identity-panel" data-testid="voice-identity-panel">
      <PanelHeading title="Voice Identity" tip="Create, select, or approve a voice identity for this character." as="h2" />

      {hasApprovedVoice && approvedVoice && (
        <div className="vip-approved-banner" data-testid="vip-approved-voice">
          <div className="vip-approved-banner__header">
            <strong>Approved Voice</strong>
            <span className="muted"> — {approvedVoice.name}</span>
          </div>
          <p className="muted">Character: {approvedVoice.characterName || selectedCharacterName}</p>
          {approvedVoice.audioUrl ? (
            <audio controls src={approvedVoice.audioUrl} data-testid="vip-approved-audio" />
          ) : null}
          <p className="muted">
            Approved:{" "}
            {approvedVoice.approvedAt
              ? new Date(approvedVoice.approvedAt).toLocaleDateString()
              : " — "}
          </p>
        </div>
      )}

      {errors.length > 0 && (
        <div className="vip-errors" data-testid="vip-errors">
          {errors.map((e, i) => (
            <p key={i} className="vip-error">
              {e}
            </p>
          ))}
        </div>
      )}

      <div className="vip-section" data-testid="vip-character-section">
        <label className="vip-label">
          Select Character
          <select
            className="vip-select"
            data-testid="vs-character-select"
            value={selectedCharacterId}
            onChange={(e) => {
              const val = e.target.value;
              if (val === "__new__") {
                setCreatingCharacter(true);
              } else {
                setSelectedCharacterId(val);
                const char = characters.find((c) => c.id === val);
                setSelectedCharacterName(char?.name || char?.characterName || "");
                setCreatingCharacter(false);
              }
            }}
          >
            <option value="">Select a character...</option>
            {characters.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name || c.characterName || c.id}
              </option>
            ))}
            <option value="__new__">Create New Character</option>
          </select>
        </label>
        {creatingCharacter && (
          <div className="vip-inline-create">
            <input
              className="vip-input"
              data-testid="vs-new-character-name"
              placeholder="New character name"
              value={newCharName}
              onChange={(e) => setNewCharName(e.target.value)}
            />
            <Button data-testid="vs-create-character-btn" onClick={handleCreateCharacter}>
              Create
            </Button>
          </div>
        )}
      </div>

      <div className="vip-section" data-testid="vip-method-section">
        <PanelHeading title="Choose Voice Method" tip="Pick one way to get a voice." as="h3" />
        <div className="vip-method-grid">
          {METHOD_CARDS.map((card) => (
            <button
              key={card.id}
              type="button"
              className={"vip-method-card" + (method === card.id ? " selected" : "")}
              data-testid={"vs-method-" + card.id}
              onClick={() => setMethod(card.id)}
            >
              <span className="vip-method-icon">{card.icon}</span>
              <strong>{card.label}</strong>
              <span className="muted">{card.description}</span>
            </button>
          ))}
        </div>
      </div>

      {method === "create" && (
        <div className="vip-section" data-testid="vip-basics-section">
          <PanelHeading title="Voice Basics" tip="Set the fundamental voice characteristics." as="h3" />

          <label className="vip-label">
            Sex
            <div className="vip-toggle-group" data-testid="vs-sex">
              <button
                type="button"
                className={"vip-toggle" + (sex === "female" ? " selected" : "")}
                onClick={() => setSex("female")}
              >
                Female
              </button>
              <button
                type="button"
                className={"vip-toggle" + (sex === "male" ? " selected" : "")}
                onClick={() => setSex("male")}
              >
                Male
              </button>
            </div>
          </label>

          <label className="vip-label">
            Age Range
            <select className="vip-select" data-testid="vs-age" value={age} onChange={(e) => setAge(e.target.value)}>
              {AGE_OPTIONS.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      <div className="vip-section" data-testid="vip-script-section">
        <label className="vip-label">
          Script / Sample Text
          <div className="vip-sample-toolbar">
            <select
              className="vip-select"
              data-testid="vs-sample-preset"
              defaultValue=""
              onChange={(e) => {
                const val = e.target.value;
                if (val) {
                  const found = SAMPLE_LINES.find((s) => s.id === val);
                  if (found) setScript(found.text);
                }
              }}
            >
              <option value="">Use Sample...</option>
              {SAMPLE_LINES.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.id.charAt(0).toUpperCase() + s.id.slice(1)}
                </option>
              ))}
            </select>
          </div>
          <textarea
            className="vip-textarea"
            rows={4}
            data-testid="vs-script"
            placeholder="Enter the line the character should speak..."
            value={script}
            onChange={(e) => setScript(e.target.value)}
          />
        </label>
      </div>

      <div className="vip-section" data-testid="vip-prompt-section">
        <label className="vip-label">
          Voice Prompt Details
          <textarea
            className="vip-textarea"
            rows={4}
            data-testid="vs-prompt-details"
            placeholder="Describe what the voice should sound like..."
            value={promptDetails}
            onChange={(e) => setPromptDetails(e.target.value)}
          />
        </label>
        <Button
          data-testid="vs-refine-prompt"
          disabled={refineLoading || !promptDetails.trim()}
          onClick={handleRefinePrompt}
        >
          {refineLoading ? "Refining..." : "Refine with Co-Director"}
        </Button>
        {refinePreview !== null && (
          <div className="vip-refine-preview" data-testid="vip-refine-preview">
            <p className="vip-refine-preview__text">{refinePreview}</p>
            <div className="vip-actions">
              <Button data-testid="vip-accept-refine" variant="primary" onClick={handleAcceptRefine}>
                Accept
              </Button>
              <Button data-testid="vip-reject-refine" onClick={handleRejectRefine}>
                Reject
              </Button>
            </div>
          </div>
        )}
      </div>

      <details
        className="vip-accordion"
        open={expanded}
        onToggle={(e) => setExpanded((e.target as HTMLDetailsElement).open)}
        data-testid="vs-advanced-controls"
      >
        <summary>Advanced Voice Controls</summary>

        <div className="vip-gauge" data-testid="vs-emotion">
          <label className="vip-gauge-label">Emotional Expression</label>
          <input
            type="range"
            min={-2}
            max={2}
            step={1}
            value={emotion}
            onChange={(e) => setEmotion(Number(e.target.value))}
          />
          <div className="vip-gauge-labels">
            <span>-2 Anger</span>
            <span>-1 Sadness</span>
            <span>0 Neutral</span>
            <span>+1 Cheerful</span>
            <span>+2 Excited</span>
          </div>
        </div>

        <div className="vip-gauge" data-testid="vs-intensity">
          <label className="vip-gauge-label">Emotional Intensity</label>
          <input
            type="range"
            min={-5}
            max={5}
            step={1}
            value={intensity}
            onChange={(e) => setIntensity(Number(e.target.value))}
          />
          <div className="vip-gauge-labels vip-gauge-labels--numeric">
            {[-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5].map((n) => (
              <span key={n}>{n}</span>
            ))}
          </div>
        </div>

        <div className="vip-gauge" data-testid="vs-speed">
          <label className="vip-gauge-label">Speaking Speed</label>
          <input
            type="range"
            min={-5}
            max={5}
            step={1}
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
          />
          <div className="vip-gauge-labels vip-gauge-labels--numeric">
            {[-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5].map((n) => (
              <span key={n}>{n}</span>
            ))}
          </div>
        </div>

        <div className="vip-gauge" data-testid="vs-pitch">
          <label className="vip-gauge-label">Pitch</label>
          <input
            type="range"
            min={-5}
            max={5}
            step={1}
            value={pitch}
            onChange={(e) => setPitch(Number(e.target.value))}
          />
          <div className="vip-gauge-labels vip-gauge-labels--numeric">
            {[-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5].map((n) => (
              <span key={n}>{n}</span>
            ))}
          </div>
        </div>
      </details>

      <div className="vip-section" data-testid="vip-archetype-section">
        <label className="vip-label">
          Character Archetype
          <select
            className="vip-select"
            data-testid="vs-archetype"
            value={archetype}
            onChange={(e) => setArchetype(e.target.value)}
          >
            {ARCHETYPES.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="vip-section" data-testid="vip-accent-section">
        <label className="vip-label">
          Accent
          <select
            className="vip-select"
            data-testid="vs-accent"
            value={accent}
            onChange={(e) => setAccent(e.target.value)}
          >
            {ACCENTS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="vip-section" data-testid="vip-sample-count-section">
        <label className="vip-label">
          Number of Samples
          <div className="vip-sample-count-selector" data-testid="vs-sample-count">
            {([1, 2, 3, 4] as const).map((n) => (
              <button
                key={n}
                type="button"
                className={"vip-sample-count-btn" + (sampleCount === n ? " selected" : "")}
                onClick={() => setSampleCount(n)}
              >
                {n}
              </button>
            ))}
          </div>
        </label>
      </div>

      <div className="vip-section" data-testid="vip-generate-section">
        <Button
          variant="primary"
          className="vip-generate-btn"
          data-testid="vs-generate"
          disabled={generationState === "generating"}
          onClick={handleGenerate}
        >
          {generationState === "generating" ? "GENERATING..." : "GENERATE VOICE SAMPLES"}
        </Button>
      </div>

      {generationState === "done" && samples.length > 0 && (
        <div className="vip-section" data-testid="vip-samples-section">
          <PanelHeading title="Generated Samples" tip="Listen and approve a voice sample." as="h3" />
          <div className="vip-samples-grid">
            {samples.map((sample, i) => (
              <div key={sample.id} className="vip-sample-card" data-testid={"vs-sample-" + i}>
                <strong>Sample {i + 1}</strong>
                <p className="muted">Status: {sample.status}</p>
                {sample.audioUrl ? (
                  <audio controls src={sample.audioUrl} />
                ) : (
                  <p className="muted">No audio available</p>
                )}
                <Button
                  data-testid={"vs-approve-" + i}
                  variant="primary"
                  disabled={hasApprovedVoice}
                  onClick={() => handleApprove(sample.id)}
                >
                  APPROVE
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
