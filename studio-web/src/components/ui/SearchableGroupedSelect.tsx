import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";

export type SearchableGroupedSelectOption = {
  value: string;
  label: string;
  description?: string;
  title?: string;
  keywords?: string[];
};

export type SearchableGroupedSelectGroup = {
  label: string;
  options: SearchableGroupedSelectOption[];
};

type FlatOption = SearchableGroupedSelectOption & {
  groupLabel: string;
};

export function SearchableGroupedSelect({
  ariaLabel,
  groups,
  value,
  customValue = "",
  placeholder = "Choose an option",
  searchPlaceholder = "Search options",
  customOptionValue = "custom",
  customInputLabel = "Custom",
  customInputPlaceholder = "Describe your custom option",
  emptyMessage = "No matches found.",
  disabled = false,
  onValueChange,
  onCustomValueChange,
}: {
  ariaLabel: string;
  groups: SearchableGroupedSelectGroup[];
  value: string;
  customValue?: string;
  placeholder?: string;
  searchPlaceholder?: string;
  customOptionValue?: string;
  customInputLabel?: string;
  customInputPlaceholder?: string;
  emptyMessage?: string;
  disabled?: boolean;
  onValueChange: (value: string, option: SearchableGroupedSelectOption | null) => void;
  onCustomValueChange: (value: string) => void;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const triggerId = useId();
  const listboxId = useId();
  const customInputId = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(0);

  const normalizedQuery = query.trim().toLowerCase();
  const filteredGroups = useMemo(() => {
    if (!normalizedQuery) return groups;
    return groups
      .map((group) => ({
        ...group,
        options: group.options.filter((option) => {
          const haystack = [
            group.label,
            option.label,
            option.description,
            option.title,
            ...(option.keywords || []),
          ]
            .filter(Boolean)
            .join(" ")
            .toLowerCase();
          return haystack.includes(normalizedQuery);
        }),
      }))
      .filter((group) => group.options.length > 0);
  }, [groups, normalizedQuery]);

  const flatOptions = useMemo<FlatOption[]>(
    () =>
      filteredGroups.flatMap((group) =>
        group.options.map((option) => ({
          ...option,
          groupLabel: group.label,
        })),
      ),
    [filteredGroups],
  );

  const selectedOption = useMemo(
    () =>
      groups
        .flatMap((group) => group.options)
        .find((option) => option.value === value) || null,
    [groups, value],
  );
  const isCustom = value === customOptionValue;
  const selectedLabel =
    isCustom && customValue.trim()
      ? customValue.trim()
      : selectedOption?.label || (isCustom ? `${customInputLabel}: ${customValue || "Not named yet"}` : placeholder);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  useEffect(() => {
    if (!open) {
      setQuery("");
      return;
    }
    const selectedIndex = flatOptions.findIndex((option) => option.value === value);
    setHighlightedIndex(selectedIndex >= 0 ? selectedIndex : 0);
    const timer = window.setTimeout(() => searchRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [flatOptions, open, value]);

  useEffect(() => {
    if (highlightedIndex > flatOptions.length - 1) {
      setHighlightedIndex(Math.max(0, flatOptions.length - 1));
    }
  }, [flatOptions.length, highlightedIndex]);

  const commitSelection = (option: SearchableGroupedSelectOption | null) => {
    if (!option) return;
    onValueChange(option.value, option);
    setOpen(false);
  };

  const moveHighlight = (direction: 1 | -1) => {
    if (!flatOptions.length) return;
    setHighlightedIndex((current) => {
      if (direction === 1) return current >= flatOptions.length - 1 ? 0 : current + 1;
      return current <= 0 ? flatOptions.length - 1 : current - 1;
    });
  };

  const onTriggerKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp" || event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setOpen(true);
    }
  };

  const onSearchKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      moveHighlight(1);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      moveHighlight(-1);
      return;
    }
    if (event.key === "Home") {
      event.preventDefault();
      setHighlightedIndex(0);
      return;
    }
    if (event.key === "End") {
      event.preventDefault();
      setHighlightedIndex(Math.max(0, flatOptions.length - 1));
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      commitSelection(flatOptions[highlightedIndex] || null);
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      const trigger = document.getElementById(triggerId);
      if (trigger instanceof HTMLButtonElement) trigger.focus();
    }
  };

  return (
    <div className={`sgs${open ? " is-open" : ""}`} ref={rootRef}>
      <button
        id={triggerId}
        type="button"
        className="sgs__trigger"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listboxId}
        disabled={disabled}
        title={selectedOption?.title || selectedOption?.description || undefined}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={onTriggerKeyDown}
      >
        <span className={`sgs__trigger-label${selectedOption || isCustom ? "" : " is-placeholder"}`}>{selectedLabel}</span>
        <span className="sgs__trigger-caret" aria-hidden="true">
          {open ? "▲" : "▼"}
        </span>
      </button>

      {open ? (
        <div className="sgs__popover">
          <label className="sgs__search">
            <span className="sgs__sr-only">Search {ariaLabel}</span>
            <input
              ref={searchRef}
              type="search"
              value={query}
              placeholder={searchPlaceholder}
              aria-controls={listboxId}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={onSearchKeyDown}
            />
          </label>

          <div className="sgs__list" id={listboxId} role="listbox" aria-label={ariaLabel}>
            {filteredGroups.length ? (
              filteredGroups.map((group) => (
                <div className="sgs__group" key={group.label} role="group" aria-label={group.label}>
                  <div className="sgs__group-label">{group.label}</div>
                  <div className="sgs__group-options">
                    {group.options.map((option) => {
                      const flatIndex = flatOptions.findIndex((item) => item.value === option.value);
                      const active = flatIndex === highlightedIndex;
                      const selected = option.value === value;
                      return (
                        <button
                          key={option.value}
                          id={`${listboxId}-${option.value}`}
                          type="button"
                          role="option"
                          aria-selected={selected}
                          className={`sgs__option${selected ? " is-selected" : ""}${active ? " is-active" : ""}`}
                          title={option.title || option.description || undefined}
                          onMouseEnter={() => setHighlightedIndex(flatIndex)}
                          onClick={() => commitSelection(option)}
                        >
                          <span>{option.label}</span>
                          {option.description ? <small>{option.description}</small> : null}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))
            ) : (
              <div className="sgs__empty">{emptyMessage}</div>
            )}
          </div>
        </div>
      ) : null}

      {isCustom ? (
        <label className="field sgs__custom" htmlFor={customInputId}>
          <span>{customInputLabel}</span>
          <input
            id={customInputId}
            value={customValue}
            placeholder={customInputPlaceholder}
            onChange={(event) => onCustomValueChange(event.target.value)}
          />
        </label>
      ) : null}
    </div>
  );
}
