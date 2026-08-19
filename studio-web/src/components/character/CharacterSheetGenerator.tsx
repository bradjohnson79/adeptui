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
import type { CharacterGeneratorPlan } from "./characterGeneratorPlan";
import { normalizeCharacterCandidate, viewIsFinished, type CharacterCandidate, type CharacterProfile, type GeneratorOption } from "./types";

type Phase = "idle" | "starting" | "generating";

type Props = {
  projectId: string;
  characterId: string;
  profile: CharacterProfile | null;
  plan: CharacterGeneratorPlan;
  localOptions?: GeneratorOption[];
  apiOptions?: GeneratorOption[];
  hasReference?: boolean;
  disabled?: boolean;
  onCandidates: (candidates: CharacterCandidate[]) => void;
  retryHandlerRef?: { current: ((candidate: CharacterCandidate) => void) | null };
  generateHandlerRef?: { current: (() => void) | null };
};

function readCandidates(pack: unknown): CharacterCandidate[] {
  const p = pack as {
    pack?: { candidates?: unknown[]; previousCandidates?: unknown[] };
    candidates?: unknown[];
    previousCandidates?: unknown[];
  } | undefined;
  const current = p?.pack?.candidates || p?.candidates || [];
  const previous = p?.pack?.previousCandidates || p?.previousCandidates || [];
  const seen = new Set<string>();
  const out: CharacterCandidate[] = [];
  for (const raw of [...current, ...previous]) {
    const c = normalizeCharacterCandidate(raw);
    const key = String(c.sheetAssetId || c.assetId || c.jobId || "");
    if (key && seen.has(key)) continue;
    if (key) seen.add(key);
    out.push(c);
  }
  return out;
}

function viewsTerminal(c: CharacterCandidate): boolean {
  const views = c.viewJobs || [];
  if (!views.length) {
    const status = String(c.status || "").trim().toLowerCase();
    return status === "failed" || status === "error" || status === "cancelled" || status === "done" || !!c.sheetAssetId || !!c.assetId;
  }
  return views.every(viewIsFinished);
}

export function CharacterSheetGenerator({
  projectId,
  characterId,
  profile,
  plan,
  localOptions = [],
  apiOptions = [],
  hasReference = false,
  disabled,
  onCandidates,
  retryHandlerRef,
  generateHandlerRef,
}: Props) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [message, setMessage] = useState("");
  const [candidates, setCandidates] = useState<CharacterCandidate[]>([]);
  const inFlightRef = useRef(false);

  const generating = phase !== "idle";
  const anyEnabled = plan.localEnabled || plan.apiEnabled;
  const blockReason = characterGenerateBlockReason({
    name: profile?.name,
    plan,
    generating,
    disabled,
    localOptions,
  });
  const canGenerate = !blockReason && !generating && !disabled;

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
        const pack = (adv as { pack?: { candidates?: CharacterCandidate[]; status?: string }; status?: string }).pack
          || (adv as { candidates?: CharacterCandidate[]; status?: string });
        const cands = readCandidates(adv);
        if (cands.length) {
          setCandidates(cands);
          onCandidates(cands);
        }
        const packStatus = String(pack?.status || "").toUpperCase();
        const allDone = cands.length > 0 && cands.every(viewsTerminal);
        if (
          allDone ||
          packStatus === "FAILED" ||
          packStatus === "READY_FOR_OWNER" ||
          packStatus === "OWNER_APPROVED" ||
          packStatus === "OWNER_APPROVED_WITH_PENDING"
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

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await api.getCharacterVisualSheet(projectId, characterId);
        const cands = readCandidates(res);
        if (!cancelled) {
          setCandidates(cands);
          onCandidates(cands);
          // GET returns the last saved pack and does not hydrate live job
          // status. Resume the existing advance poller so failed imagegen
          // jobs leave "Generating..." without a second poller.
          if (cands.length && !cands.every(viewsTerminal) && !inFlightRef.current) {
            inFlightRef.current = true;
            setPhase("generating");
            setMessage("Generating…");
            void poll(180);
          }
        }
      } catch {
        /* no pack yet */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, characterId, onCandidates, poll]);

  const generate = useCallback(async () => {
    if (inFlightRef.current) return;
    const reason = characterGenerateBlockReason({
      name: profile?.name,
      plan,
      generating: false,
      disabled,
      localOptions,
    });
    if (reason) {
      setMessage(reason);
      return;
    }
    inFlightRef.current = true;
    setPhase("starting");
    setMessage("Starting…");
    try {
      const body = buildCharacterSheetStartBody({
        profileVisualStyle: profile?.visual_style,
        plan,
        hasReference,
        localOptions,
        apiOptions,
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
  }, [disabled, projectId, characterId, profile, plan, hasReference, localOptions, apiOptions, onCandidates, poll]);

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
  if (generateHandlerRef) {
    generateHandlerRef.current = () => {
      void generate();
    };
  }

  const buttonLabel =
    phase === "starting" ? "Starting…" : phase === "generating" ? "Generating…" : "Generate Character Reference Sheet";

  return (
    <div className="character-core__generate">
      {generating ? (
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
