import { useEffect, useState } from "react";
import type { Asset } from "../../types";
import { referencePresentation, type ImageRole } from "./referenceRole";

export function LibraryReferenceControl({
  asset,
  busy,
  error,
  onClassify,
  onUse,
}: {
  asset: Asset;
  busy: boolean;
  error?: string;
  onClassify: (approvedAs: ImageRole | null) => void;
  onUse: () => void;
}) {
  const view = referencePresentation(asset);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    window.addEventListener("pointerdown", close);
    return () => window.removeEventListener("pointerdown", close);
  }, [open]);

  if (view.source === "media") {
    return (
      <button type="button" className="film-ref-role__badge" data-testid="film-reference-role" onClick={onUse}>
        <span className="film-ref-role__check" data-testid="film-reference-check" aria-hidden="true">✓</span> {view.badge}
      </button>
    );
  }

  return (
    <div className="film-ref-role" onPointerDown={(event) => event.stopPropagation()}>
      {view.badge ? (
        <button type="button" className="film-ref-role__badge" data-testid="film-reference-role" onClick={onUse}>
          <span className="film-ref-role__check" data-testid="film-reference-check" aria-hidden="true">✓</span> {view.badge}
        </button>
      ) : null}
      {view.note ? (
        <em className="film-ref-role__note" data-testid="film-reference-note">
          {view.note}
        </em>
      ) : null}
      {error ? (
        <em className="film-ref-role__error" data-testid="film-reference-error">
          {error}
        </em>
      ) : null}
      {view.menuLabel ? (
        <div className="film-ref-role__menu">
          <button
            type="button"
            data-testid={view.menuLabel === "Reference As" ? "film-reference-as" : "film-reference-change"}
            aria-expanded={open}
            disabled={busy}
            onClick={() => setOpen((value) => !value)}
          >
            {view.menuLabel}
          </button>
          {open ? (
            <div className="film-ref-role__list" role="menu">
              {view.options.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  role="menuitem"
                  data-testid={
                    option.id === "clear"
                      ? "film-reference-remove"
                      : option.id === "reset"
                        ? "film-reference-reset"
                        : `film-reference-set-${option.approvedAs}`
                  }
                  onClick={() => {
                    setOpen(false);
                    onClassify(option.approvedAs);
                  }}
                >
                  {option.label}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
