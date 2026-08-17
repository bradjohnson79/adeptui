import { useMemo, useRef, useState } from "react";
import { ReferenceTokenAutocomplete } from "./ReferenceTokenAutocomplete";
import {
  countBindingsByKind,
  displayToken,
  isRealBindingId,
  mediaKindForType,
  tokenAtCaret,
  type ReferenceBindingView,
} from "../../sceneReferences/referenceTokens";

export function PromptReferenceField({
  text,
  bindingIds,
  bindings,
  maxImages,
  maxVideos,
  onTextChange,
  onTextFocus,
  onTextBlur,
  onBindingsChange,
  onReject,
  ensureBinding,
}: {
  text: string;
  bindingIds: string[];
  bindings: ReferenceBindingView[];
  maxImages?: number | null;
  maxVideos?: number | null;
  onTextChange: (next: string) => void;
  onTextFocus?: () => void;
  onTextBlur?: () => void;
  onBindingsChange: (ids: string[]) => void;
  onReject: (message: string) => void;
  ensureBinding?: (binding: ReferenceBindingView) => Promise<ReferenceBindingView | null>;
}) {
  const areaRef = useRef<HTMLTextAreaElement | null>(null);
  const [draft, setDraft] = useState("");
  const [relinkId, setRelinkId] = useState<string | null>(null);
  const counts = countBindingsByKind(bindingIds, bindings);
  const caretToken = tokenAtCaret(text, areaRef.current?.selectionStart ?? text.length);

  const addBinding = async (binding: ReferenceBindingView, insertToken = true) => {
    const resolved = ensureBinding
      ? await ensureBinding(binding)
      : isRealBindingId(binding.id)
        ? binding
        : null;
    if (!resolved || !isRealBindingId(resolved.id)) {
      onReject("Pick a named reference from this project's References.");
      return;
    }
    const kind = resolved.media_kind || mediaKindForType(resolved.reference_type);
    if (kind === "image" && typeof maxImages === "number" && maxImages >= 0 && counts.image >= maxImages) {
      onReject(`This generator supports up to ${maxImages} image references for this clip.`);
      return;
    }
    if (kind === "video" && typeof maxVideos === "number" && maxVideos >= 0 && counts.video >= maxVideos) {
      onReject(`This generator supports up to ${maxVideos} video references for this clip.`);
      return;
    }
    const nextIds = bindingIds.includes(resolved.id) ? bindingIds : [...bindingIds, resolved.id];
    onBindingsChange(nextIds);
    if (insertToken) {
      const token = displayToken(resolved.alias || resolved.asset_name, resolved.media_kind);
      const el = areaRef.current;
      const pos = el?.selectionStart ?? text.length;
      const at = tokenAtCaret(text, pos);
      if (at) {
        onTextChange(`${text.slice(0, at.start)}${token}${text.slice(at.end)}`);
      } else if (!text.includes(token)) {
        onTextChange(text ? `${text.trimEnd()} ${token}` : token);
      }
    }
    setDraft("");
  };

  const relinkOptions = useMemo(() => {
    if (!relinkId) return [];
    const broken = bindings.find((item) => item.id === relinkId);
    const want = broken?.media_kind || "image";
    return bindings.filter((item) => isRealBindingId(item.id) && (item.media_kind || mediaKindForType(item.reference_type)) === want);
  }, [bindings, relinkId]);

  return (
    <div className="prompt-ref-field" data-testid="prompt-reference-field">
      <textarea
        ref={areaRef}
        data-testid="timeline-prompt-instruction"
        value={text}
        onChange={(e) => onTextChange(e.target.value)}
        onFocus={onTextFocus}
        onBlur={onTextBlur}
      />
      <div className="prompt-ref-field__counts" data-testid="prompt-ref-counts">
        {typeof maxImages === "number" ? `Image refs ${counts.image} / ${maxImages}` : null}
        {typeof maxImages === "number" && typeof maxVideos === "number" ? " · " : null}
        {typeof maxVideos === "number" ? `Video refs ${counts.video} / ${maxVideos}` : null}
        {counts.entity ? `${typeof maxImages === "number" || typeof maxVideos === "number" ? " · " : ""}Entities ${counts.entity}` : null}
      </div>
      <div className="prompt-ref-field__chips" data-testid="prompt-ref-chips">
        {bindingIds.map((id) => {
          const binding = bindings.find((item) => item.id === id);
          const broken = !binding || Boolean(binding.broken);
          const label = broken
            ? `Broken Reference${binding?.alias ? ` ${binding.alias}` : ""}`
            : displayToken(binding.alias || binding.asset_name, binding.media_kind);
          return (
            <span key={id} className={`prompt-ref-chip${broken ? " prompt-ref-chip--broken" : ""}`} data-testid={`prompt-ref-chip-${id}`}>
              {label}
              {broken ? (
                <button type="button" className="ghost" onClick={() => setRelinkId(id)}>
                  Relink
                </button>
              ) : null}
              <button
                type="button"
                className="ghost"
                aria-label="Remove reference"
                onClick={() => onBindingsChange(bindingIds.filter((item) => item !== id))}
              >
                ×
              </button>
            </span>
          );
        })}
      </div>
      {relinkId ? (
        <select
          data-testid="prompt-ref-relink"
          value=""
          onChange={(e) => {
            const next = e.target.value;
            if (!next) return;
            onBindingsChange(bindingIds.map((id) => (id === relinkId ? next : id)));
            setRelinkId(null);
          }}
        >
          <option value="">Relink to…</option>
          {relinkOptions.map((item) => (
            <option key={item.id} value={item.id}>
              {displayToken(item.alias || item.asset_name, item.media_kind)}
            </option>
          ))}
        </select>
      ) : null}
      <ReferenceTokenAutocomplete
        value={draft || (caretToken ? `${caretToken.prefix}${caretToken.query}` : "")}
        bindings={bindings}
        track="prompt"
        placeholder="@ character  # image  * video"
        onChange={setDraft}
        onCommit={(binding) => void addBinding(binding, true)}
        onReject={onReject}
      />
    </div>
  );
}
