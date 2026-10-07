import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";

export type TrackVolumeControlProps = {
  trackLabel: string;
  volumePercent: number;
  muted: boolean;
  disabled?: boolean;
  onChange: (volumePercent: number) => void;
  onToggleMute: () => void;
};

export function stepVolumePercent(
  current: number,
  shiftKey: boolean,
  key: "ArrowUp" | "ArrowRight" | "ArrowDown" | "ArrowLeft",
): number {
  const delta = shiftKey ? 5 : 1;
  const increasing = key === "ArrowUp" || key === "ArrowRight";
  const next = increasing ? current + delta : current - delta;
  return Math.max(0, Math.min(100, next));
}

function SpeakerIcon({ state, label }: { state: "normal" | "reduced" | "muted"; label: string }) {
  const common = {
    width: 14,
    height: 14,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.4,
    role: "img",
    "aria-label": label,
  } as const;
  return (
    <svg {...common}>
      <title>{label}</title>
      <path d="M3 6.5h2.2L9 3.5v9L5.2 9.5H3z" />
      {state === "normal" ? (
        <>
          <path d="M11 5c1.5 1.5 1.5 4.5 0 6" />
          <path d="M13 3c2.5 2.5 2.5 7.5 0 10" />
        </>
      ) : state === "reduced" ? (
        <path d="M11 5c1.5 1.5 1.5 4.5 0 6" />
      ) : (
        <path d="M11 6.5l3 3M14 6.5l-3 3" />
      )}
    </svg>
  );
}

export function TrackVolumeControl({
  trackLabel,
  volumePercent,
  muted,
  disabled = false,
  onChange,
  onToggleMute,
}: TrackVolumeControlProps) {
  const { t } = useTranslation("timeline");
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(volumePercent);
  const draftRef = useRef(draft);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const percentButtonRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const sliderRef = useRef<HTMLInputElement>(null);
  const [popoverPos, setPopoverPos] = useState<{ top: number; left: number } | null>(null);

  useEffect(() => {
    draftRef.current = draft;
  }, [draft]);

  useEffect(() => {
    if (!open) return;
    setDraft(volumePercent);
    draftRef.current = volumePercent;
  }, [open, volumePercent]);

  // The popover is portaled to document.body and positioned fixed so it can
  // never be clipped by the track lane's overflow. Anchor it to the percent
  // button and keep it fully inside the viewport.
  const updatePopoverPosition = useCallback(() => {
    const btn = percentButtonRef.current;
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    const popoverWidth = 192; // ~10.5rem slider + padding/readout
    const popoverHeight = 44;
    const margin = 8;
    const maxLeft = Math.max(margin, window.innerWidth - popoverWidth - margin);
    const left = Math.min(Math.max(rect.left, margin), maxLeft);
    let top = rect.bottom + 6;
    if (top + popoverHeight > window.innerHeight - margin) {
      top = Math.max(margin, rect.top - popoverHeight - 6);
    }
    setPopoverPos({ top, left });
  }, []);

  useEffect(() => {
    if (!open) return;
    updatePopoverPosition();
    window.addEventListener("scroll", updatePopoverPosition, true);
    window.addEventListener("resize", updatePopoverPosition);
    return () => {
      window.removeEventListener("scroll", updatePopoverPosition, true);
      window.removeEventListener("resize", updatePopoverPosition);
    };
  }, [open, updatePopoverPosition]);

  // Focus once the portal has actually rendered (popoverPos set), so arrow
  // keys adjust the slider immediately without a Tab.
  useEffect(() => {
    if (open && popoverPos) sliderRef.current?.focus();
  }, [open, popoverPos]);

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(e: PointerEvent) {
      const target = e.target as Node;
      if (wrapperRef.current?.contains(target) || popoverRef.current?.contains(target)) {
        return;
      }
      setOpen(false);
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        percentButtonRef.current?.focus();
      }
    }
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  const iconState: "normal" | "reduced" | "muted" = muted ? "muted" : volumePercent < 50 ? "reduced" : "normal";

  const muteLabel = muted ? "Unmute" : "Mute";

  const volumeLabel = t("trackVolumeLabel", {
    track: trackLabel,
    percent: volumePercent,
    defaultValue: `${trackLabel} volume, ${volumePercent} percent`,
  });

  const disabledTitle = disabled
    ? t("trackVolumeDisabled", { track: trackLabel, defaultValue: `Add a clip to set ${trackLabel} volume` })
    : undefined;

  function commit(nextPercent: number) {
    if (nextPercent !== volumePercent) {
      onChange(Math.max(0, Math.min(100, nextPercent)));
    }
  }

  return (
    <div ref={wrapperRef} className="timeline-v2__track-volume" title={disabledTitle}>
      <button
        type="button"
        ref={percentButtonRef}
        className="timeline-v2__track-volume-btn timeline-v2__track-volume-btn--percent"
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={volumeLabel}
        disabled={disabled}
        onPointerDown={(event) => event.stopPropagation()}
        onClick={() => {
          if (disabled) return;
          setOpen((prev) => !prev);
        }}
      >
        <span className="timeline-v2__track-volume-readout" aria-hidden>
          {volumePercent}%
        </span>
      </button>
      {open && popoverPos
        ? createPortal(
            <div
              ref={popoverRef}
              className="timeline-v2__track-volume-popover"
              role="dialog"
              style={{ top: popoverPos.top, left: popoverPos.left }}
              aria-label={t("trackVolumePopoverLabel", {
                track: trackLabel,
                defaultValue: `${trackLabel} volume`,
              })}
            >
              <input
                ref={sliderRef}
                type="range"
                min={0}
                max={100}
                step={1}
                value={draft}
                className="timeline-v2__track-volume-slider"
                aria-label={t("trackVolumeSliderLabel", {
                  track: trackLabel,
                  percent: draft,
                  defaultValue: `${trackLabel} volume, ${draft} percent`,
                })}
                onChange={(e) => setDraft(Number(e.target.value))}
                onPointerUp={() => commit(draft)}
                onKeyDown={(e) => {
                  if (["ArrowUp", "ArrowRight", "ArrowDown", "ArrowLeft"].includes(e.key)) {
                    e.preventDefault();
                    const next = stepVolumePercent(draftRef.current, e.shiftKey, e.key as "ArrowUp" | "ArrowRight" | "ArrowDown" | "ArrowLeft");
                    draftRef.current = next;
                    setDraft(next);
                  }
                }}
                onKeyUp={(e) => {
                  if (["ArrowUp", "ArrowRight", "ArrowDown", "ArrowLeft"].includes(e.key)) {
                    commit(draftRef.current);
                  }
                }}
              />
              <span className="timeline-v2__track-volume-popover-readout" aria-hidden>
                {draft}%
              </span>
            </div>,
            document.body,
          )
        : null}
      <button
        type="button"
        className="timeline-v2__track-volume-btn timeline-v2__track-volume-btn--mute"
        aria-pressed={muted}
        aria-label={muteLabel}
        title={muteLabel}
        disabled={disabled}
        onPointerDown={(event) => event.stopPropagation()}
        onClick={() => {
          if (disabled) return;
          setOpen(false);
          onToggleMute();
        }}
      >
        <SpeakerIcon state={muted ? "muted" : iconState} label={muteLabel} />
      </button>
    </div>
  );
}
