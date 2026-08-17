import { useMemo, useState } from "react";
import {
  bindingAcceptedOnTrack,
  formatAutocompleteRow,
  parseTokenQuery,
  prefixForMediaKind,
  type ReferenceBindingView,
} from "../../sceneReferences/referenceTokens";

export function ReferenceTokenAutocomplete({
  value,
  bindings,
  track,
  onChange,
  onCommit,
  onReject,
  placeholder,
}: {
  value: string;
  bindings: ReferenceBindingView[];
  track: "imageReference" | "videoReference";
  onChange: (next: string) => void;
  onCommit: (binding: ReferenceBindingView) => void;
  onReject: (message: string) => void;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const parsed = parseTokenQuery(value);
  const rows = useMemo(() => {
    const q = parsed.query.toLowerCase();
    return bindings.filter((binding) => {
      const prefix = prefixForMediaKind(binding.media_kind);
      if (parsed.prefix && prefix !== parsed.prefix) return false;
      if (!q) return Boolean(parsed.prefix);
      const alias = (binding.alias || binding.asset_name || "").toLowerCase();
      const token = (binding.display_token || "").toLowerCase();
      return alias.includes(q) || token.includes(q);
    });
  }, [bindings, parsed.prefix, parsed.query]);

  const commit = (binding: ReferenceBindingView) => {
    if (!bindingAcceptedOnTrack(binding, track)) {
      onReject(
        track === "videoReference"
          ? "Video Reference only accepts * video tokens."
          : "Image Reference only accepts # image or @ character/prop tokens.",
      );
      return;
    }
    onCommit(binding);
    setOpen(false);
  };

  return (
    <div className="ref-token-autocomplete" data-testid={`ref-token-autocomplete-${track}`}>
      <input
        value={value}
        placeholder={placeholder}
        aria-label={track === "videoReference" ? "Video reference token" : "Image reference token"}
        data-testid={`ref-token-input-${track}`}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && rows[0]) {
            e.preventDefault();
            commit(rows[0]);
          }
          if (e.key === "Escape") setOpen(false);
        }}
        onClick={(e) => e.stopPropagation()}
      />
      {open && value.trim() ? (
        <ul className="ref-token-autocomplete__list" data-testid={`ref-token-results-${track}`}>
          {rows.length === 0 ? (
            <li className="ref-token-autocomplete__empty">No matching references</li>
          ) : (
            rows.map((binding) => (
              <li key={binding.id}>
                <button
                  type="button"
                  className="ref-token-autocomplete__row"
                  data-testid={`ref-token-row-${binding.id}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    commit(binding);
                  }}
                >
                  {formatAutocompleteRow(binding)}
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}
