/**
 * CharacterSheetGenerator — drives the 4-view Character Sheet candidate
 * generation. Enqueues candidates, polls for completion, and exposes the
 * resulting composed-sheet candidates for selection.
 *
 * User Control Law: only enqueues to the enabled source pools. If neither
 * source is enabled, generation is a no-op.
 */
import { useCallback, useRef, useState } from "react";
import { api } from "../../api";
import { GenerationProgressBar } from "./GenerationProgressBar";
import type { CharacterCandidate, CharacterProfile, GeneratorSourceState } from "./types";

type Sources = { local: GeneratorSourceState; api: GeneratorSourceState };

type Props = {
  projectId: string;
  characterId: string;
  profile: CharacterProfile | null;
  sources: Sources;
  disabled?: boolean;
  onCandidates: (candidates: CharacterCandidate[]) => void;
  retryHandlerRef?: { current: ((candidate: CharacterCandidate) => void) | null };
};

function readCandidates(pack: unknown): CharacterCandidate[] {
  const p = pack as { candidates?: CharacterCandidate[] } | undefined;
  return (p?.candidates || []) as CharacterCandidate[];
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
  disabled,
  onCandidates,
  retryHandlerRef,
}: Props) {
  const [generating, setGenerating] = useState(false);
  const [message, setMessage] = useState("");
  const [candidates, setCandidates] = useState<CharacterCandidate[]>([]);
  const pollingRef = useRef(false);

  const anyEnabled = sources.local.enabled || sources.api.enabled;
  const canGenerate =
    !!profile?.name?.trim() && anyEnabled && !generating && !disabled;

  const poll = useCallback(
    async (attemptsLeft: number) => {
      if (attemptsLeft <= 0) {
        pollingRef.current = false;
        setGenerating(false);
        setMessage("");
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
        // Keep polling until every required view is terminal (16 views for a 4x4 pack).
        const allDone = cands.length > 0 && cands.every(viewsTerminal);
        if (
          allDone ||
          pack?.status === "READY_FOR_OWNER" ||
          pack?.status === "OWNER_APPROVED"
        ) {
          pollingRef.current = false;
          setGenerating(false);
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
    if (!canGenerate || pollingRef.current) return;
    setGenerating(true);
    setMessage("Generating character sheets…");
    onCandidates([]);
    setCandidates([]);
    try {
      const res = await api.startCharacterVisualSheet(projectId, characterId, {
        candidateCount: 4,
        visualStyle: profile?.visual_style || undefined,
        includeDetails: false,
        includePerformance: false,
        // User Control Law: pass enabled source pools only.
        generatorSources: {
          local: sources.local.enabled
            ? {
                family: sources.local.selectedId || undefined,
                stage2Family: sources.local.stage2Enabled
                  ? sources.local.stage2SelectedId || undefined
                  : undefined,
                stage2Enabled: sources.local.stage2Enabled || false,
              }
            : null,
          api: sources.api.enabled ? { model: sources.api.selectedId || undefined } : null,
        },
      } as Record<string, unknown>);
      const initial = readCandidates((res as { pack?: unknown }).pack);
      setCandidates(initial);
      onCandidates(initial);
      pollingRef.current = true;
      void poll(180);
    } catch (e) {
      setGenerating(false);
      setMessage(e instanceof Error ? e.message : "Generation failed to start.");
    }
  }, [canGenerate, projectId, characterId, profile, sources, onCandidates, poll]);

  const retryCandidate = useCallback(
    async (candidate: CharacterCandidate) => {
      const idx = candidate.candidateIndex;
      if (idx == null) return;
      setGenerating(true);
      setMessage("Retrying failed candidate…");
      try {
        const res = await api.retryCharacterVisualSheetCandidate(projectId, characterId, idx);
        const next = readCandidates((res as { pack?: unknown }).pack);
        if (next.length) {
          setCandidates(next);
          onCandidates(next);
        }
        if (!pollingRef.current) {
          pollingRef.current = true;
          void poll(180);
        }
      } catch (e) {
        if (!pollingRef.current) setGenerating(false);
        setMessage(e instanceof Error ? e.message : "Retry failed to start.");
      }
    },
    [projectId, characterId, onCandidates, poll],
  );

  if (retryHandlerRef) {
    retryHandlerRef.current = (c) => {
      void retryCandidate(c);
    };
  }

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
        {generating ? "Generating…" : "Generate Character Sheet"}
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
