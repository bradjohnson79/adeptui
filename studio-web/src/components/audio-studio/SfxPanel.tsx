import { useEffect, useState } from "react";
import { HelpTip } from "../HelpTip";
import { Button } from "../ui";
import { AdvancedDrawer } from "./AdvancedDrawer";
import { CandidateCard } from "./CandidateCard";
import { GenerationProgressBar } from "./GenerationProgressBar";
import {
  SFX_ADHERENCE,
  SFX_ADVANCED_FIELD_META,
  SFX_DISTANCES,
  SFX_MATERIALS,
  SFX_PACES,
  SFX_PERSPECTIVES,
  SFX_PHYSICAL_EVENTS,
  SFX_REFINE_BUTTONS,
  SFX_REVERBS,
  honorBadge,
  type SfxDirectorIntent,
} from "./sfxIntent";
import type { AudioCandidate, AudioGenerationProgress } from "./types";

type SfxPanelProps = {
  busy: boolean;
  sourceReady: boolean;
  sourceLabel: string;
  generationProgress?: AudioGenerationProgress | null;
  onCancelGeneration?: () => Promise<void> | void;
  durationSec: number;
  intensity: string;
  eventType: string;
  prompt: string;
  candidateCount: 1 | 2 | 3;
  intent: SfxDirectorIntent;
  advancedOpen: boolean;
  refiningOp?: string | null;
  candidates: AudioCandidate[];
  previewAssetId?: string | null;
  approvedAssetIds: Record<string, boolean>;
  onDurationChange: (value: number) => void;
  onIntensityChange: (value: string) => void;
  onEventTypeChange: (value: string) => void;
  onPromptChange: (value: string) => void;
  onCandidateCountChange: (value: 1 | 2 | 3) => void;
  onIntentChange: (next: SfxDirectorIntent) => void;
  onAdvancedToggle: () => void;
  onGenerate: () => Promise<void> | void;
  onRefine: (op: string) => Promise<void> | void;
  onPreview: (candidate: AudioCandidate) => void;
  onApprove: (candidate: AudioCandidate) => Promise<void> | void;
};

const INTENSITIES = ["Subtle", "Normal", "Bold"] as const;
const STARTERS = [
  { label: "Door slam", eventType: "door_slam", prompt: "Heavy steel door slam, close." },
  { label: "Footsteps", eventType: "footsteps_walk", prompt: "Footsteps on metal grating, mid-distance." },
  { label: "Glass on counter", eventType: "glass_place", prompt: "Glass set on a counter, short and clean." },
  { label: "Electrical spark", eventType: "electrical_spark", prompt: "Electrical spark and arcing." },
];

function patchIntent(
  intent: SfxDirectorIntent,
  patch: Omit<Partial<SfxDirectorIntent>, "temporal"> & {
    temporal?: Partial<SfxDirectorIntent["temporal"]>;
  },
): SfxDirectorIntent {
  return {
    ...intent,
    ...patch,
    temporal: {
      ...intent.temporal,
      ...(patch.temporal || {}),
    },
    negatives: patch.negatives ?? intent.negatives,
    refinementOps: patch.refinementOps ?? intent.refinementOps,
  };
}

function FieldHonor({ fieldKey }: { fieldKey: string }) {
  const meta = SFX_ADVANCED_FIELD_META.find((row) => row.key === fieldKey);
  if (!meta) return null;
  return (
    <span className={`audio-honor audio-honor--${meta.honor}`} title={meta.hint}>
      {honorBadge(meta.honor)}
    </span>
  );
}

export function SfxPanel({
  busy,
  sourceReady,
  sourceLabel,
  generationProgress = null,
  durationSec,
  intensity,
  eventType,
  prompt,
  candidateCount,
  intent,
  advancedOpen,
  refiningOp = null,
  candidates,
  previewAssetId,
  approvedAssetIds,
  onDurationChange,
  onIntensityChange,
  onEventTypeChange,
  onPromptChange,
  onCandidateCountChange,
  onIntentChange,
  onAdvancedToggle,
  onGenerate,
  onRefine,
  onCancelGeneration,
  onPreview,
  onApprove,
}: SfxPanelProps) {
  const [negativesDraft, setNegativesDraft] = useState(intent.negatives.join(", "));

  useEffect(() => {
    setNegativesDraft(intent.negatives.join(", "));
  }, [intent.negatives]);

  const syncNegatives = (raw: string) => {
    setNegativesDraft(raw);
    const negatives = raw
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean);
    onIntentChange(patchIntent(intent, { negatives }));
  };

  const advancedSummary = [
    intent.physicalEvent || "event auto",
    intent.material || "material auto",
    intent.distance || null,
    intent.reverb ? `reverb ${intent.reverb}` : null,
    intent.temporal.pace ? `pace ${intent.temporal.pace}` : null,
    intent.negatives.length ? `${intent.negatives.length} negatives` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <section className="audio-studio-panel" data-testid="audio-sfx-panel">
      <div className="audio-studio-panel__hero">
        <div>
          <h3>Sound Effects</h3>
          <p className="muted">Name the moment. Advanced stays optional — MMAudio honors structure via prompt.</p>
        </div>
        <span className={`audio-source${sourceReady ? " is-ready" : " is-blocked"}`}>{sourceLabel}</span>
      </div>

      <div className="audio-chip-row">
        {STARTERS.map((item) => (
          <button
            key={item.label}
            type="button"
            className={`audio-chip${eventType === item.eventType || intent.physicalEvent === item.eventType ? " is-selected" : ""}`}
            data-testid={`audio-sfx-preset-${item.eventType}`}
            onClick={() => {
              onEventTypeChange(item.eventType);
              onPromptChange(item.prompt);
              onIntentChange(
                patchIntent(intent, {
                  physicalEvent: item.eventType,
                  temporal: { ...intent.temporal, durationSec },
                }),
              );
            }}
          >
            {item.label}
          </button>
        ))}
      </div>

      <label className="audio-field audio-field--full">
        <span className="audio-field__label">
          What happens?
          <HelpTip text="Say what you hear in plain language. The Sound Engine turns that into a detailed sound description for you." />
        </span>
        <textarea
          rows={3}
          value={prompt}
          onChange={(e) => {
            // ORDER 12: typed text always wins — clear chip selection + physicalEvent lock.
            onEventTypeChange("");
            onPromptChange(e.target.value);
            onIntentChange(patchIntent(intent, { physicalEvent: "" }));
          }}
          placeholder="Metallic door slam, close, heavy."
          data-testid="audio-sfx-prompt"
        />
      </label>

      <div className="audio-form-grid audio-form-grid--compact">
        <label className="audio-field">
          <span className="audio-field__label">
            How long?
            <HelpTip text="Clip length in seconds. Native MMAudio duration control." />
          </span>
          <input
            type="number"
            min={1}
            max={12}
            step={1}
            value={durationSec}
            onChange={(e) => {
              const next = Number(e.target.value) || 2;
              onDurationChange(next);
              onIntentChange(patchIntent(intent, { temporal: { durationSec: next } }));
            }}
            data-testid="audio-sfx-duration"
          />
        </label>
        <label className="audio-field">
          <span className="audio-field__label">
            Strength
            <HelpTip text="Subtle / Normal / Bold — compiled into the MMAudio prompt." />
          </span>
          <select
            value={intensity}
            onChange={(e) => {
              onIntensityChange(e.target.value);
              onIntentChange(patchIntent(intent, { intensity: e.target.value.toLowerCase() }));
            }}
            data-testid="audio-sfx-strength"
          >
            {INTENSITIES.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
        <label className="audio-field">
          <span className="audio-field__label">Takes</span>
          <select
            value={candidateCount}
            onChange={(e) => onCandidateCountChange(Number(e.target.value) as 1 | 2 | 3)}
            data-testid="audio-sfx-takes"
          >
            <option value={1}>1</option>
            <option value={2}>2</option>
            <option value={3}>3</option>
          </select>
        </label>
      </div>

      <AdvancedDrawer
        open={advancedOpen}
        title="Advanced sound controls"
        summary={advancedSummary || "Optional structure. Prompt-influenced on MMAudio — not mixer knobs."}
        onToggle={onAdvancedToggle}
      >
        <p className="muted audio-advanced__matrix-note" data-testid="audio-sfx-honor-note">
          MMAudio is prompt + duration native. Advanced fields below are labeled honestly per the ORDER 14 honor matrix.
        </p>
        <div className="audio-form-grid" data-testid="audio-sfx-advanced-fields">
          <label className="audio-field">
            <span className="audio-field__label">Physical event <FieldHonor fieldKey="physicalEvent" /></span>
            <select
              value={intent.physicalEvent}
              onChange={(e) => {
                const physicalEvent = e.target.value;
                onEventTypeChange(physicalEvent);
                onIntentChange(patchIntent(intent, { physicalEvent }));
              }}
              data-testid="audio-sfx-physical-event"
            >
              <option value="">Auto from What happens</option>
              {SFX_PHYSICAL_EVENTS.map((event) => (
                <option key={event} value={event}>{event}</option>
              ))}
            </select>
          </label>
          <label className="audio-field">
            <span className="audio-field__label">Material <FieldHonor fieldKey="material" /></span>
            <select
              value={intent.material}
              onChange={(e) => onIntentChange(patchIntent(intent, { material: e.target.value }))}
              data-testid="audio-sfx-material"
            >
              <option value="">Auto</option>
              {SFX_MATERIALS.filter(Boolean).map((material) => (
                <option key={material} value={material}>{material}</option>
              ))}
            </select>
          </label>
          <label className="audio-field audio-field--full">
            <span className="audio-field__label">Context <FieldHonor fieldKey="context" /></span>
            <input
              type="text"
              value={intent.context}
              onChange={(e) => onIntentChange(patchIntent(intent, { context: e.target.value }))}
              placeholder="Interior hallway, kitchen, Foley booth…"
              data-testid="audio-sfx-context"
            />
          </label>
          <label className="audio-field audio-field--full">
            <span className="audio-field__label">Environment <FieldHonor fieldKey="environment" /></span>
            <input
              type="text"
              value={intent.environment || ""}
              onChange={(e) => onIntentChange(patchIntent(intent, { environment: e.target.value }))}
              placeholder="Small room, outdoor street, bathroom…"
              data-testid="audio-sfx-environment"
            />
          </label>
          <label className="audio-field">
            <span className="audio-field__label">Event count <FieldHonor fieldKey="eventCount" /></span>
            <input
              type="number"
              min={1}
              max={64}
              value={intent.temporal.eventCount ?? ""}
              placeholder="auto"
              onChange={(e) => {
                const raw = e.target.value.trim();
                const eventCount = raw === "" ? null : Math.max(1, Number(raw) || 1);
                onIntentChange(patchIntent(intent, { temporal: { eventCount } }));
              }}
              data-testid="audio-sfx-event-count"
            />
          </label>
          <label className="audio-field">
            <span className="audio-field__label">Pace <FieldHonor fieldKey="pace" /></span>
            <select
              value={intent.temporal.pace ?? ""}
              onChange={(e) => {
                const pace = (e.target.value || null) as SfxDirectorIntent["temporal"]["pace"];
                onIntentChange(patchIntent(intent, { temporal: { pace } }));
              }}
              data-testid="audio-sfx-pace"
            >
              <option value="">Auto</option>
              {SFX_PACES.map((pace) => (
                <option key={pace} value={pace}>{pace}</option>
              ))}
            </select>
          </label>
          <label className="audio-field">
            <span className="audio-field__label">Continuous <FieldHonor fieldKey="continuous" /></span>
            <select
              value={intent.temporal.continuous === null || intent.temporal.continuous === undefined ? "" : intent.temporal.continuous ? "yes" : "no"}
              onChange={(e) => {
                const raw = e.target.value;
                const continuous = raw === "" ? null : raw === "yes";
                onIntentChange(patchIntent(intent, { temporal: { continuous } }));
              }}
              data-testid="audio-sfx-continuous"
            >
              <option value="">Auto</option>
              <option value="yes">Yes (stream)</option>
              <option value="no">No (discrete)</option>
            </select>
          </label>
          <label className="audio-field">
            <span className="audio-field__label">Distance <FieldHonor fieldKey="distance" /></span>
            <select
              value={intent.distance || ""}
              onChange={(e) => onIntentChange(patchIntent(intent, { distance: e.target.value as SfxDirectorIntent["distance"] }))}
              data-testid="audio-sfx-distance"
            >
              <option value="">Auto</option>
              {SFX_DISTANCES.map((distance) => (
                <option key={distance} value={distance}>{distance}</option>
              ))}
            </select>
          </label>
          <label className="audio-field">
            <span className="audio-field__label">Perspective <FieldHonor fieldKey="perspective" /></span>
            <select
              value={intent.perspective || ""}
              onChange={(e) => onIntentChange(patchIntent(intent, { perspective: e.target.value as SfxDirectorIntent["perspective"] }))}
              data-testid="audio-sfx-perspective"
            >
              <option value="">Auto</option>
              {SFX_PERSPECTIVES.map((perspective) => (
                <option key={perspective} value={perspective}>{perspective}</option>
              ))}
            </select>
          </label>
          <label className="audio-field">
            <span className="audio-field__label">Reverb <FieldHonor fieldKey="reverb" /></span>
            <select
              value={intent.reverb || ""}
              onChange={(e) => onIntentChange(patchIntent(intent, { reverb: e.target.value as SfxDirectorIntent["reverb"] }))}
              data-testid="audio-sfx-reverb"
            >
              <option value="">Auto</option>
              {SFX_REVERBS.map((reverb) => (
                <option key={reverb} value={reverb}>{reverb}</option>
              ))}
            </select>
          </label>
          <label className="audio-field">
            <span className="audio-field__label">Adherence <FieldHonor fieldKey="adherence" /></span>
            <select
              value={intent.adherence || ""}
              onChange={(e) => onIntentChange(patchIntent(intent, { adherence: e.target.value as SfxDirectorIntent["adherence"] }))}
              data-testid="audio-sfx-adherence"
            >
              <option value="">Balanced default</option>
              {SFX_ADHERENCE.map((adherence) => (
                <option key={adherence} value={adherence}>{adherence}</option>
              ))}
            </select>
          </label>
          <label className="audio-field audio-field--full">
            <span className="audio-field__label">Negatives (comma-separated) <FieldHonor fieldKey="negatives" /></span>
            <textarea
              rows={2}
              value={negativesDraft}
              onChange={(e) => syncNegatives(e.target.value)}
              placeholder="knock, gunshot, whoosh…"
              data-testid="audio-sfx-negatives"
            />
          </label>
        </div>
      </AdvancedDrawer>

      <div className="audio-studio-panel__footer">
        <Button
          variant="primary"
          loading={busy}
          disabled={!sourceReady || !prompt.trim()}
          onClick={() => void onGenerate()}
          data-testid="audio-sfx-generate"
        >
          {`Generate ${candidateCount} ${candidateCount === 1 ? "Sound" : "Sounds"}`}
        </Button>
        <GenerationProgressBar
          visible={Boolean(generationProgress?.visible || busy)}
          percent={generationProgress?.percent ?? 0}
          label={generationProgress?.label || (busy ? "Starting…" : "Ready")}
          active={Boolean(busy || generationProgress?.active)}
          onCancel={onCancelGeneration}
        />
      </div>

      <section className="audio-sfx-refine" data-testid="audio-sfx-refine">
        <div className="audio-sfx-refine__header">
          <strong>Refine take</strong>
          <p className="muted">Owner ops call mutate-intent (candidate path preferred). Does not rewrite What happens by hand.</p>
        </div>
        <div className="audio-chip-row audio-sfx-refine__ops">
          {SFX_REFINE_BUTTONS.map((item) => {
            const active = refiningOp === item.op;
            return (
              <button
                key={item.op}
                type="button"
                className={`audio-chip${active ? " is-selected" : ""}`}
                data-testid={`audio-sfx-refine-${item.op}`}
                disabled={busy || !prompt.trim()}
                title={item.label}
                onClick={() => void onRefine(item.op)}
              >
                {item.label}
              </button>
            );
          })}
        </div>
      </section>

      {candidates.length ? (
        <div className="audio-candidate-grid">
          {candidates.map((candidate) => (
            <CandidateCard
              key={candidate.id}
              candidate={candidate}
              ctaLabel="Sound"
              busy={busy}
              previewSelected={previewAssetId === (candidate.assetId || candidate.id)}
              approved={Boolean(candidate.assetId && approvedAssetIds[candidate.assetId])}
              onPreview={() => onPreview(candidate)}
              onApprove={() => onApprove(candidate)}
            />
          ))}
        </div>
      ) : (
        <div className="audio-empty-state">
          <strong>Your sounds will appear here.</strong>
          <p className="muted">Play a sound, select it, then approve it.</p>
        </div>
      )}
    </section>
  );
}
