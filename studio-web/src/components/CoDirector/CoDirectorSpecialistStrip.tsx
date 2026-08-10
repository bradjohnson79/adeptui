import { useEffect, useState } from "react";
import { api } from "../../api";
import { useCoDirectorSession } from "./CoDirectorSession";

type SpecialistOption = { id: string; displayName: string };

export function CoDirectorSpecialistStrip() {
  const { uiContext } = useCoDirectorSession();
  const [specialists, setSpecialists] = useState<SpecialistOption[]>([]);
  const [selectedId, setSelectedId] = useState<string>("character-creator");
  const [readiness, setReadiness] = useState<{
    score?: number;
    nextAction?: string;
    blockers?: string[];
    status?: string;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .m211Specialists()
      .then((res) => {
        if (cancelled) return;
        const inventory = (res?.specialists || []) as Array<{ id?: string; displayName?: string }>;
        const opts = inventory
          .filter((s) => s.id)
          .map((s) => ({ id: s.id!, displayName: s.displayName || s.id!.replace(/-/g, " ") }));
        setSpecialists(opts);
        if (opts.some((o) => o.id === "character-creator")) {
          setSelectedId("character-creator");
        } else if (opts.length) {
          setSelectedId(opts[0].id);
        }
      })
      .catch(() => {
        if (!cancelled) setSpecialists([{ id: "character-creator", displayName: "Character Creator" }]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const characterId = uiContext.selectedCharacterIds?.[0];

  useEffect(() => {
    const projectId = uiContext.projectId;
    if (!projectId || selectedId !== "character-creator" || !characterId) {
      setReadiness(null);
      return;
    }
    let cancelled = false;
    api
      .getCharacterCoverage(projectId, characterId)
      .then((cov) => {
        if (cancelled) return;
        setReadiness({
          score: typeof cov?.score === "number" ? cov.score : undefined,
          nextAction: cov?.next_action || cov?.guidance?.[0] || "",
          blockers: cov?.critical_blockers || [],
          status: cov?.status,
        });
      })
      .catch(() => {
        if (!cancelled) setReadiness(null);
      });
    return () => {
      cancelled = true;
    };
  }, [uiContext.projectId, characterId, selectedId]);

  if (!specialists.length) return null;

  const selected = specialists.find((s) => s.id === selectedId);

  return (
    <div className="codirector-specialist-strip" data-testid="codirector-specialist-strip">
      <label className="codirector-specialist-select">
        <span className="muted">Specialist</span>
        <select
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          aria-label="Select Co-Director specialist"
          data-testid="codirector-specialist-select"
        >
          {specialists.map((s) => (
            <option key={s.id} value={s.id}>
              {s.displayName}
            </option>
          ))}
        </select>
      </label>
      {selectedId === "character-creator" && readiness && (
        <div className="codirector-readiness-strip" data-testid="codirector-character-readiness">
          <span>
            {readiness.status?.replace(/_/g, " ") || "Draft"}
            {typeof readiness.score === "number" ? ` · ${Math.round(readiness.score * 100)}%` : ""}
          </span>
          {readiness.blockers?.length ? (
            <span className="codirector-readiness-blocker" title={readiness.blockers.join("; ")}>
              Blocker: {readiness.blockers[0]}
            </span>
          ) : readiness.nextAction ? (
            <span>Next: {readiness.nextAction}</span>
          ) : null}
        </div>
      )}
      {selected && selectedId !== "character-creator" ? (
        <span className="muted">{selected.displayName} active</span>
      ) : null}
    </div>
  );
}
