import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";

export type VoiceStudioSelectOption = {
  value: string;
  label: string;
  disabled?: boolean;
};

type Props = {
  value: string;
  options: VoiceStudioSelectOption[];
  onChange: (value: string) => void;
  ariaLabel: string;
  testId?: string;
  disabled?: boolean;
  placeholder?: string;
};

function nextEnabledIndex(options: VoiceStudioSelectOption[], from: number, direction: 1 | -1): number {
  if (!options.length) return 0;
  let index = from;
  for (let step = 0; step < options.length; step += 1) {
    index = (index + direction + options.length) % options.length;
    if (!options[index]?.disabled) return index;
  }
  return Math.max(0, from);
}

export function VoiceStudioSelect({
  value,
  options,
  onChange,
  ariaLabel,
  testId,
  disabled = false,
  placeholder = "Choose…",
}: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const typeaheadRef = useRef({ buffer: "", at: 0 });
  const triggerId = useId();
  const listboxId = useId();
  const [open, setOpen] = useState(false);
  const selectedIndex = useMemo(
    () => Math.max(0, options.findIndex((option) => option.value === value)),
    [options, value],
  );
  const [highlightedIndex, setHighlightedIndex] = useState(selectedIndex);
  const selected = options.find((option) => option.value === value);
  const selectedLabel = selected?.label || placeholder;

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    setHighlightedIndex(selectedIndex);
    const option = listRef.current?.querySelector<HTMLElement>("[data-highlighted='true']");
    option?.scrollIntoView({ block: "nearest" });
  }, [open, selectedIndex]);

  useEffect(() => {
    if (!open) return;
    const option = listRef.current?.querySelector<HTMLElement>("[data-highlighted='true']");
    option?.scrollIntoView({ block: "nearest" });
  }, [highlightedIndex, open]);

  const commit = (option: VoiceStudioSelectOption | undefined) => {
    if (!option || option.disabled) return;
    onChange(option.value);
    setOpen(false);
  };

  const jumpByQuery = (letter: string) => {
    const now = Date.now();
    const state = typeaheadRef.current;
    state.buffer = now - state.at < 500 ? `${state.buffer}${letter}` : letter;
    state.at = now;
    const query = state.buffer.toLowerCase();
    const start = highlightedIndex + 1;
    for (let offset = 0; offset < options.length; offset += 1) {
      const index = (start + offset) % options.length;
      const option = options[index];
      if (option && !option.disabled && option.label.toLowerCase().startsWith(query)) {
        setHighlightedIndex(index);
        return;
      }
    }
  };

  const onKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return;
    if (!open && (event.key === "ArrowDown" || event.key === "ArrowUp" || event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      setOpen(true);
      return;
    }
    if (!open) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlightedIndex((current) => nextEnabledIndex(options, current, 1));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightedIndex((current) => nextEnabledIndex(options, current, -1));
      return;
    }
    if (event.key === "Home") {
      event.preventDefault();
      setHighlightedIndex(options.findIndex((option) => !option.disabled));
      return;
    }
    if (event.key === "End") {
      event.preventDefault();
      for (let index = options.length - 1; index >= 0; index -= 1) {
        if (!options[index]?.disabled) {
          setHighlightedIndex(index);
          return;
        }
      }
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      commit(options[highlightedIndex]);
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      return;
    }
    if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault();
      jumpByQuery(event.key);
    }
  };

  return (
    <div className={`vss${open ? " is-open" : ""}`} ref={rootRef}>
      <button
        id={triggerId}
        type="button"
        className="vss__trigger"
        data-testid={testId}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listboxId}
        disabled={disabled}
        onClick={() => !disabled && setOpen((current) => !current)}
        onKeyDown={onKeyDown}
      >
        <span className={`vss__label${selected ? "" : " is-placeholder"}`}>{selectedLabel}</span>
        <span className="vss__caret" aria-hidden="true">
          {open ? "▲" : "▼"}
        </span>
      </button>
      {open ? (
        <div
          ref={listRef}
          id={listboxId}
          className="vss__list"
          role="listbox"
          aria-label={ariaLabel}
          data-testid={testId ? `${testId}-list` : undefined}
        >
          {options.map((option, index) => {
            const selectedOption = option.value === value;
            const highlighted = index === highlightedIndex;
            return (
              <button
                key={option.value || `empty-${index}`}
                type="button"
                role="option"
                aria-selected={selectedOption}
                disabled={option.disabled}
                data-highlighted={highlighted ? "true" : "false"}
                data-testid={testId ? `${testId}-option` : undefined}
                className={
                  "vss__option" +
                  (selectedOption ? " is-selected" : "") +
                  (highlighted ? " is-active" : "")
                }
                onMouseEnter={() => setHighlightedIndex(index)}
                onClick={() => commit(option)}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
