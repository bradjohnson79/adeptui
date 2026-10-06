import { useEffect, useMemo, useRef, useState } from "react";
import {
  filterAddReferenceCandidates,
  formatAddReferenceRow,
  isAlreadyBound,
  type AddReferenceCandidate,
  type BoundIdentity,
} from "../../sceneReferences/referenceAddCandidates";

export function ReferencesAddInput({
  candidates,
  bound,
  onSelect,
  onActivity,
  disabled,
}: {
  candidates: AddReferenceCandidate[];
  bound: BoundIdentity[];
  onSelect: (candidate: AddReferenceCandidate) => void | Promise<boolean | void>;
  /** Clears parent pane bind/lookup errors while the user types or gets fresh matches. */
  onActivity?: () => void;
  disabled?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const [status, setStatus] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const rows = useMemo(
    () => filterAddReferenceCandidates(candidates, query),
    [candidates, query],
  );

  useEffect(() => {
    setHighlight(0);
  }, [query, rows.length]);

  // Clear stale "No matching reference" once candidates arrive (async race).
  useEffect(() => {
    if (rows.length > 0 && status === "No matching reference") setStatus(null);
  }, [rows.length, status]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const commit = async (candidate: AddReferenceCandidate) => {
    if (isAlreadyBound(candidate, bound)) {
      setStatus("Already added");
      return;
    }
    setStatus(null);
    const result = await onSelect(candidate);
    const ok = result !== false;
    if (!ok) {
      // Parent sets bind-fail messaging ("Could not add reference"); keep query for retry.
      return;
    }
    setQuery("");
    setOpen(false);
    setHighlight(0);
    inputRef.current?.focus();
  };

  const showList = open && query.trim().length > 0;

  return (
    <div className="field references-add" ref={rootRef} data-testid="references-add">
      <label htmlFor="references-add-input">Add Reference</label>
      <input
        id="references-add-input"
        ref={inputRef}
        data-testid="references-add-input"
        value={query}
        disabled={disabled}
        placeholder="Type @character, %prop, #environment, *video, or &audio..."
        autoComplete="off"
        aria-autocomplete="list"
        aria-controls="references-add-results"
        aria-expanded={showList}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setStatus(null);
          onActivity?.();
        }}
        onKeyDown={(e) => {
          if (!showList && e.key !== "Escape") return;
          if (e.key === "ArrowDown") {
            e.preventDefault();
            if (!rows.length) return;
            setHighlight((i) => (i + 1) % rows.length);
            setOpen(true);
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            if (!rows.length) return;
            setHighlight((i) => (i - 1 + rows.length) % rows.length);
            setOpen(true);
          } else if (e.key === "Enter") {
            e.preventDefault();
            const row = rows[highlight] || rows[0];
            if (row) void commit(row);
            else if (query.trim()) setStatus("No matching reference");
          } else if (e.key === "Escape") {
            e.preventDefault();
            setOpen(false);
            setStatus(null);
          }
        }}
      />
      {status ? (
        <p className="scene-meta" data-testid="references-add-status" role="status">
          {status}
        </p>
      ) : null}
      {showList ? (
        <ul
          id="references-add-results"
          className="ref-token-autocomplete__list references-add__results"
          data-testid="references-add-results"
          role="listbox"
        >
          {rows.length === 0 ? (
            <li className="ref-token-autocomplete__empty" data-testid="references-add-empty">{candidates.length === 0 ? "No reference candidates loaded" : "No matching reference"}</li>
          ) : (
            rows.map((row, index) => {
              const already = isAlreadyBound(row, bound);
              return (
                <li key={row.assetId} role="option" aria-selected={index === highlight}>
                  <button
                    type="button"
                    className={`ref-token-autocomplete__row${index === highlight ? " is-highlighted" : ""}${already ? " is-disabled" : ""}`}
                    data-testid={`references-add-row-${row.assetId}`}
                    data-semantic-type={row.semanticType}
                    data-scope={row.scopeLabel}
                    data-already={already ? "true" : "false"}
                    disabled={already}
                    title={already ? "Already added" : formatAddReferenceRow(row)}
                    onMouseEnter={() => setHighlight(index)}
                    onClick={(e) => {
                      e.preventDefault();
                      if (already) {
                        setStatus("Already added");
                        return;
                      }
                      void commit(row);
                    }}
                  >
                    {row.thumbnailUrl ? (
                      <img
                        src={row.thumbnailUrl}
                        alt=""
                        width={24}
                        height={24}
                        style={{ objectFit: "cover", marginRight: 8, verticalAlign: "middle" }}
                      />
                    ) : null}
                    <span dir="auto">{row.displayToken}</span>
                    <span className="scene-meta">
                      {" "}
                      Â· {row.semanticType === "character" ? "Character" : row.semanticType === "prop" ? "Prop" : row.semanticType === "environment" ? "Environment" : row.semanticType === "video" ? "Video" : row.semanticType === "audio" ? "Audio" : row.semanticType} Â·{" "}
                      {row.scopeLabel}
                      {already ? " Â· Already added" : ""}
                    </span>
                  </button>
                </li>
              );
            })
          )}
        </ul>
      ) : null}
    </div>
  );
}
