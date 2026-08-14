/**
 * CharacterSheetGenerator — drives the 4-view Character Sheet candidate
 * generation. Enqueues candidates, polls for completion, and exposes the
 * resulting composed-sheet candidates for selection.
 *
 * User Control Law: only enqueues to the enabled source pools. If neither
 * source is enabled, generation is refused with a visible error.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import { GenerationProgressBar } from "./GenerationProgressBar";
import {
  buildCharacterSheetStartBody,
  characterGenerateBlockReason,
  formatCharacterSheetStartError,
} from "./characterSheetGenerate";
import type { CharacterCandidate, CharacterProfile, GeneratorSourceState } from "./types";

type Sources = { local: GeneratorSourceState; api: GeneratorSourceState };
type Phase = "idle" | "starting" | "generating";

type Props = {
  projectId: string;
  characterId: string;
  profile: CharacterProfile | null;
  sources: Sources;
  hasReference?: boolean;
  disabled?: boolean;
  onCandidates: (candidates: CharacterCandidate[]) => void;
  retryHandlerRef?: { current: ((candidate: CharacterCandidate) => void) | null };
};

function readCandidates(pack: unknown): CharacterCandidate[] {
  const p = pack as { pack?: { candidates?: CharacterCandidate[] }; candidates?: CharacterCandidate[] } | undefined;
  return (p?.pack?.candidates || p?.candidates || []) as CharacterCandidate[];
}

function viewsTerminal(c: CharacterCandidate): boolean {
  const views = c.viewJobs || [];
  if (!views.length) {
    return c.status === "failed" || c.status === "done" || !!c.sheetAssetId || !!c.assetId;
  }
  return views.every(
    (v) =>
      ["done", "failed", "error", "cancelled", "missing"].includes(v.status || "") || !!v.assetId,
  );
}

export function CharacterSheetGenerator({
  projectId,
  characterId,
  profile,
  sources,
  hasReference = false,
  disabled,
  onCandidates,
  retryHandlerRef,
}: Props) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [message, setMessage] = useState("");
  const [candidates, setCandidates] = useState<CharacterCandidate[]>([]);
  const inFlightRef = useRef(false);

  const generating = phase !== "idle";
  const anyEnabled = sources.local.enabled || sources.api.enabled;
  const blockReason = characterGenerateBlockReason({
    name: profile?.name,
    sources,
    generating,
    disabled,
  });
  const canGenerate = !blockReason && !generating && !disabled;

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await api.getCharacterVisualSheet(projectId, characterId);
        const cands = readCandidates(res);
        if (!cancelled && cands.length) {
          setCandidates(cands);
          onCandidates(cands);
        }
      } catch {
        /* no pack yet */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, characterId, onCandidates]);

  const poll = useCallback(
    async (attemptsLeft: number) => {
      if (attemptsLeft <= 0) {
        inFlightRef.current = false;
        setPhase("idle");
        setMessage(
          formatCharacterSheetStartError("Local runtime did not finish in time. You can retry."),
        );
        return;
      }
      try {
        const adv = await api.advanceCharacterVisualSheet(projectId, characterId);
        const pack = (adv as { pack?: { candidates?: CharacterCandidate[]; status?: string } }).pack;
        const cands = readCandidates(pack);
        if (cands.length) {
          setCandidates(cands);
          onCandidates(cands);
        }
        const allDone = cands.length > 0 && cands.every(viewsTerminal);
        if (
          allDone ||
          pack?.status === "READY_FOR_OWNER" ||
          pack?.status === "OWNER_APPROVED"
        ) {
          inFlightRef.current = false;
          setPhase("idle");
          setMessage("");
          return;
        }
      } catch {
        // transient; keep polling
      }
      setTimeout(() => void poll(attemptsLeft - 1), 2000);
    },
    [projectId, characterId, onCandidates],
  );

  const generate = useCallback(async () => {
    if (inFlightRef.current) return;
    const reason = characterGenerateBlockReason({
      name: profile?.name,
      sources,
      generating: false,
      disabled,
    });
    if (reason) {
      setMessage(reason);
      return;
    }
    inFlightRef.current = true;
    setPhase("starting");
    setMessage("Starting…");
    onCandidates([]);
    setCandidates([]);
    try {
      const body = buildCharacterSheetStartBody({
        profileVisualStyle: profile?.visual_style,
        sources,
        hasReference,
      });
      setPhase("generating");
      setMessage("Generating…");
      const res = await api.startCharacterVisualSheet(projectId, characterId, body);
      const initial = readCandidates((res as { pack?: unknown }).pack);
      setCandidates(initial);
      onCandidates(initial);
      void poll(180);
    } catch (e) {
      inFlightRef.current = false;
      setPhase("idle");
      setMessage(formatCharacterSheetStartError(e));
    }
  }, [disabled, projectId, characterId, profile, sources, hasReference, onCandidates, poll]);

  const retryCandidate = useCallback(
    async (candidate: CharacterCandidate) => {
      const idx = candidate.candidateIndex;
      if (idx == null || inFlightRef.current) return;
      inFlightRef.current = true;
      setPhase("generating");
      setMessage("Retrying failed candidate…");
      try {
        const res = await api.retryCharacterVisualSheetCandidate(projectId, characterId, idx);
        const next = readCandidates((res as { pack?: unknown }).pack);
        if (next.length) {
          setCandidates(next);
          onCandidates(next);
        }
        void poll(180);
      } catch (e) {
        inFlightRef.current = false;
        setPhase("idle");
        setMessage(formatCharacterSheetStartError(e));
      }
    },
    [projectId, characterId, onCandidates, poll],
  );

  if (retryHandlerRef) {
    retryHandlerRef.current = (c) => {
      void retryCandidate(c);
    };
  }

  const buttonLabel =
    phase === "starting" ? "Starting…" : phase === "generating" ? "Generating…" : "Generate Character Sheet";

  return (
    <div className="character-core__generate">
      {generating || candidates.length > 0 ? (
        <GenerationProgressBar candidates={candidates} active={generating} />
      ) : null}
      <button
        type="button"
        className="character-core__button primary"
        data-testid="character-generate"
        disabled={!canGenerate}
        onClick={() => void generate()}
      >
        {buttonLabel}
      </button>
      {!anyEnabled ? (
        <p className="character-core__hint" data-testid="generator-none-hint">
          Enable a Local or Cloud generator to create character sheets.
        </p>
      ) : null}
      {message ? (
        <p className="character-core__hint" data-testid="character-generate-msg">
          {message}
        </p>
      ) : null}
    </div>
  );
}
