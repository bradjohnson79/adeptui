/**
 * Shot Description field with prompt-native @ % # ~ autocomplete + ACTIVE REFERENCES strip.
 * Dropdown catalogs == autocomplete source == active tags == generation referenceAssetIds.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api";
import type { CisAuthorityRef } from "./cisAuthorityTypes";
import {
  applyAuthoritySelection,
  filterCatalogForAutocomplete,
  igTokenAtCaret,
  insertChipAtCaret,
  normalizeChipKey,
  optionToAuthorityRef,
  parseIgPromptTokens,
  resolvePromptAgainstCatalog,
  type IgCatalogOption,
} from "./igPromptTokens";

export function IgActiveReferencesStrip({
  selected,
  onChange,
  onInsertChip,
  unresolved,
  staleWarnings,
}: {
  selected: CisAuthorityRef[];
  onChange: (next: CisAuthorityRef[]) => void;
  onInsertChip: (chip: string) => void;
  unresolved: Array<{ raw: string; suggestions: string[] }>;
  staleWarnings: string[];
}) {
  return (
    <div className="cis-active-refs-strip" data-testid="cis-active-refs-strip">
      <div className="cis-active-refs-strip__header">
        <strong>Active references</strong>
        <span className="muted tiny" data-testid="cis-active-refs-strip-count">
          {selected.length} selected
        </span>
      </div>
      {!selected.length ? (
        <p className="muted tiny">No active references - type @ % # ~ in the shot description or use selectors below.</p>
      ) : (
        <ul className="cis-active-refs-strip__list">
          {selected.map((ref) => (
            <li key={ref.key} className="cis-active-refs-strip__chip" data-testid={`cis-strip-chip-${ref.key}`}>
              <img src={api.assetUrl(ref.assetId)} alt="" />
              <button
                type="button"
                className="cis-active-refs-strip__tag"
                title="Insert tag at cursor"
                data-testid={`cis-strip-insert-${ref.assetId}`}
                onClick={() => onInsertChip(ref.chip)}
              >
                <strong>{ref.chip}</strong>
                <span className="muted tiny">{ref.kind}</span>
              </button>
              <button
                type="button"
                className="ghost cis-active-refs-strip__remove"
                aria-label={`Remove ${ref.chip}`}
                data-testid={`cis-strip-remove-${ref.assetId}`}
                onClick={() => onChange(selected.filter((s) => s.key !== ref.key))}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      {unresolved.length ? (
        <div className="cis-prompt-tag-warn" data-testid="cis-unresolved-tags" role="status">
          {unresolved.map((u) => (
            <p key={u.raw} className="pill warn tiny">
              Unresolved {u.raw}
              {u.suggestions.length ? ` — Did you mean ${u.suggestions.join(", ")}?` : ""}
            </p>
          ))}
        </div>
      ) : null}
      {staleWarnings.length ? (
        <div className="cis-prompt-tag-warn" data-testid="cis-stale-env-tags" role="status">
          {staleWarnings.map((w) => (
            <p key={w} className="pill warn tiny">
              {w}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function IgShotDescriptionField({
  prompt,
  onPromptChange,
  catalogs,
  selected,
  onSelectedChange,
  unresolved,
  onUnresolvedChange,
}: {
  prompt: string;
  onPromptChange: (next: string) => void;
  catalogs: IgCatalogOption[];
  selected: CisAuthorityRef[];
  onSelectedChange: (next: CisAuthorityRef[]) => void;
  unresolved: Array<{ raw: string; suggestions: string[] }>;
  onUnresolvedChange: (next: Array<{ raw: string; suggestions: string[] }>) => void;
}) {
  const areaRef = useRef<HTMLTextAreaElement | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const [caret, setCaret] = useState(0);
  const [staleWarnings, setStaleWarnings] = useState<string[]>([]);

  const caretToken = useMemo(() => igTokenAtCaret(prompt, caret), [prompt, caret]);

  const suggestions = useMemo(() => {
    if (!caretToken) return [] as IgCatalogOption[];
    return filterCatalogForAutocomplete(catalogs, caretToken.sigil, caretToken.query);
  }, [catalogs, caretToken]);

  useEffect(() => {
    setHighlight(0);
    setMenuOpen(Boolean(caretToken && suggestions.length >= 0 && caretToken));
  }, [caretToken?.sigil, caretToken?.query, caretToken, suggestions.length]);

  const activateFromOption = useCallback(
    (opt: IgCatalogOption) => {
      const applied = applyAuthoritySelection(selected, optionToAuthorityRef(opt));
      onSelectedChange(applied.refs);
      return applied;
    },
    [onSelectedChange, selected],
  );

  const commitSuggestion = useCallback(
    (opt: IgCatalogOption) => {
      const el = areaRef.current;
      const pos = el?.selectionStart ?? caret;
      const inserted = insertChipAtCaret(prompt, pos, opt.chip);
      onPromptChange(inserted.text);
      activateFromOption(opt);
      setMenuOpen(false);
      requestAnimationFrame(() => {
        const node = areaRef.current;
        if (!node) return;
        node.focus();
        node.setSelectionRange(inserted.caret, inserted.caret);
        setCaret(inserted.caret);
      });
    },
    [activateFromOption, caret, onPromptChange, prompt],
  );

  const runResolve = useCallback(
    (text: string, refs: CisAuthorityRef[]) => {
      const result = resolvePromptAgainstCatalog(text, catalogs, refs);
      let nextRefs = refs;
      for (const add of result.toActivate) {
        nextRefs = applyAuthoritySelection(nextRefs, add).refs;
      }
      if (nextRefs !== refs && nextRefs.length !== refs.length) {
        onSelectedChange(nextRefs);
      } else if (result.toActivate.length) {
        // length may stay same under replace — still apply
        let mutated = refs;
        let changed = false;
        for (const add of result.toActivate) {
          const applied = applyAuthoritySelection(mutated, add);
          if (applied.refs !== mutated) {
            mutated = applied.refs;
            changed = true;
          }
        }
        if (changed) onSelectedChange(mutated);
      }
      onUnresolvedChange(result.unresolved);
      const warns: string[] = [];
      for (const tag of result.staleEnvTags) {
        warns.push(`Prompt still mentions inactive ${tag} after Environment replace.`);
      }
      for (const tag of result.stalePoseTags) {
        warns.push(`Prompt still mentions inactive ${tag} after reference replace.`);
      }
      setStaleWarnings(warns);
      return result;
    },
    [catalogs, onSelectedChange, onUnresolvedChange],
  );

  const insertChip = useCallback(
    (chip: string) => {
      const el = areaRef.current;
      const pos = el?.selectionStart ?? prompt.length;
      const inserted = insertChipAtCaret(prompt, pos, chip);
      if (inserted.alreadyPresent) {
        // Focus existing occurrence — move caret; subtle no-op on text.
        requestAnimationFrame(() => {
          const node = areaRef.current;
          if (!node) return;
          node.focus();
          node.setSelectionRange(inserted.caret, inserted.caret);
          setCaret(inserted.caret);
        });
        return;
      }
      onPromptChange(inserted.text);
      requestAnimationFrame(() => {
        const node = areaRef.current;
        if (!node) return;
        node.focus();
        node.setSelectionRange(inserted.caret, inserted.caret);
        setCaret(inserted.caret);
      });
    },
    [onPromptChange, prompt],
  );

  // Expose resolve for parent preflight via custom event on the textarea wrapper.
  useEffect(() => {
    const node = areaRef.current?.closest("[data-ig-prompt-root]");
    if (!node) return;
    const handler = () => {
      runResolve(prompt, selected);
    };
    node.addEventListener("ig-prompt-resolve", handler as EventListener);
    return () => node.removeEventListener("ig-prompt-resolve", handler as EventListener);
  }, [prompt, runResolve, selected]);

  return (
    <div className="ig-prompt-native" data-ig-prompt-root data-testid="ig-prompt-native">
      <div className="field ig-prompt-native__field">
        <label htmlFor="cis-prompt">Shot description</label>
        <div className="ig-prompt-native__editor">
          <textarea
            ref={areaRef}
            id="cis-prompt"
            rows={5}
            value={prompt}
            data-testid="cis-prompt"
            placeholder="Describe the shot as a filmmaker — use @Character %Prop #Environment or a Library ~ image…"
            onChange={(e) => {
              onPromptChange(e.target.value);
              setCaret(e.target.selectionStart);
            }}
            onClick={(e) => setCaret((e.target as HTMLTextAreaElement).selectionStart)}
            onKeyUp={(e) => setCaret((e.target as HTMLTextAreaElement).selectionStart)}
            onSelect={(e) => setCaret((e.target as HTMLTextAreaElement).selectionStart)}
            onBlur={() => {
              // Delay so autocomplete click can commit first.
              window.setTimeout(() => {
                setMenuOpen(false);
                runResolve(prompt, selected);
              }, 120);
            }}
            onKeyDown={(e) => {
              if (!menuOpen || !caretToken) return;
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setHighlight((h) => Math.min(h + 1, Math.max(0, suggestions.length - 1)));
                return;
              }
              if (e.key === "ArrowUp") {
                e.preventDefault();
                setHighlight((h) => Math.max(h - 1, 0));
                return;
              }
              if ((e.key === "Enter" || e.key === "Tab") && suggestions[highlight]) {
                e.preventDefault();
                commitSuggestion(suggestions[highlight]);
                return;
              }
              if (e.key === "Escape") {
                e.preventDefault();
                setMenuOpen(false);
              }
            }}
          />
          {menuOpen && caretToken ? (
            <ul
              className="ig-prompt-autocomplete"
              data-testid="ig-prompt-autocomplete"
              role="listbox"
            >
              {!suggestions.length ? (
                <li className="ig-prompt-autocomplete__empty">No matching references</li>
              ) : (
                suggestions.map((opt, idx) => (
                  <li key={opt.key}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={idx === highlight}
                      className={
                        idx === highlight
                          ? "ig-prompt-autocomplete__row is-active"
                          : "ig-prompt-autocomplete__row"
                      }
                      data-testid={`ig-ac-${opt.key}`}
                      onMouseDown={(ev) => {
                        ev.preventDefault();
                        commitSuggestion(opt);
                      }}
                    >
                      <strong>{opt.chip}</strong>
                      <span className="muted tiny">{opt.kind}{opt.hint ? ` · ${opt.hint}` : ""}</span>
                    </button>
                  </li>
                ))
              )}
            </ul>
          ) : null}
        </div>
      </div>

      <IgActiveReferencesStrip
        selected={selected}
        onChange={onSelectedChange}
        onInsertChip={insertChip}
        unresolved={unresolved}
        staleWarnings={staleWarnings}
      />

      {/* Debug-friendly payload prove hook */}
      <p className="muted tiny cis-refids-debug" data-testid="cis-refids-debug" hidden={false}>
        referenceAssetIds: {selected.map((s) => s.assetId).filter(Boolean).join(", ") || "(none)"}
        {parseIgPromptTokens(prompt).length
          ? ` · prompt tags: ${parseIgPromptTokens(prompt)
              .map((t) => t.raw)
              .join(" ")}`
          : ""}
      </p>
    </div>
  );
}

export function mergeResolvedIntoSelected(
  selected: CisAuthorityRef[],
  catalogs: IgCatalogOption[],
  prompt: string,
): { refs: CisAuthorityRef[]; unresolved: Array<{ raw: string; suggestions: string[] }>; warnings: string[] } {
  const result = resolvePromptAgainstCatalog(prompt, catalogs, selected);
  let refs = selected;
  for (const add of result.toActivate) {
    refs = applyAuthoritySelection(refs, add).refs;
  }
  const warnings: string[] = [];
  for (const tag of result.staleEnvTags) {
    warnings.push(`Prompt still mentions inactive ${tag} after Environment replace.`);
  }
  for (const tag of result.stalePoseTags) {
    warnings.push(`Prompt still mentions inactive ${tag} after reference replace.`);
  }
  // Dedupe unresolved by raw
  const seen = new Set<string>();
  const unresolved = result.unresolved.filter((u) => {
    const k = normalizeChipKey(u.raw);
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  return { refs, unresolved, warnings };
}
