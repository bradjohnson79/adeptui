import { useMemo, useState } from "react";
import {
  bindingAcceptedOnTrack,
  formatAutocompleteRow,
  parseTokenQuery,
  prefixForMediaKind,
  sortBindingsForTrack,
  type ReferenceBindingView,
  type ReferenceTrack,
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
  track: ReferenceTrack;
  onChange: (next: string) => void;
  onCommit: (binding: ReferenceBindingView) => void;
  onReject: (message: string) => void;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const parsed = parseTokenQuery(value);
  const rows = useMemo(() => {
    const q = parsed.query.toLowerCase();
    const filtered = bindings.filter((binding) => {
      if (track === "prompt" && String(binding.id || "").startsWith("character:")) return false;
      if (track === "lipsyncSpeaker" && !bindingAcceptedOnTrack(binding, "lipsyncSpeaker")) return false;
      if (track === "camera" && !bindingAcceptedOnTrack(binding, "camera")) return false;
      const prefix = prefixForMediaKind(binding.media_kind);
      if (parsed.prefix && prefix !== parsed.prefix) return false;
      if (track === "lipsyncSpeaker" && parsed.prefix && parsed.prefix !== "@") return false;
      if (track === "camera" && parsed.prefix === "#") return false;
      if (!q) return Boolean(parsed.prefix) || track === "lipsyncSpeaker" || track === "camera";
      const alias = (binding.alias || binding.asset_name || "").toLowerCase();
      const token = (binding.display_token || "").toLowerCase();
      return alias.includes(q) || token.includes(q);
    });
    return sortBindingsForTrack(filtered, track);
  }, [bindings, parsed.prefix, parsed.query, track]);

  const commit = (binding: ReferenceBindingView) => {
    if (!bindingAcceptedOnTrack(binding, track)) {
      onReject(
        track === "videoReference"
          ? "Video Reference only accepts * video tokens."
          : track === "lipsyncSpeaker"
            ? "Lip Sync only accepts @ character tokens."
            : track === "camera"
              ? "Camera uses @ characters and * video motion references."
              : track === "prompt"
                ? "Pick a named reference from this project's References."
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
        aria-label={
          track === "videoReference"
            ? "Video reference token"
            : track === "lipsyncSpeaker"
              ? "Lip Sync character"
              : track === "camera"
                ? "Camera motion reference"
                : track === "prompt"
                  ? "Prompt reference token"
                  : "Image reference token"
        }
        dir="auto"
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
                  dir="auto"
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
