/**
 * Standard additional Observed views — user/Library photographs only.
 * Generated images never count. This is not Qwen supplementary-view assist.
 */
import { useRef } from "react";

export type ObservedSlot = {
  assetId: string;
  label: string;
};

type Props = {
  masterAssetId?: string;
  views: ObservedSlot[];
  onChooseLibrary: (slot: number) => void;
  onUpload: (slot: number, file: File) => void;
  onClear?: (slot: number) => void;
  disabled?: boolean;
};

const EXTRA_SLOTS = [1, 2, 3] as const;

export function ObservedViewsPanel({
  masterAssetId,
  views,
  onChooseLibrary,
  onUpload,
  onClear,
  disabled = false,
}: Props) {
  const fileRefs = useRef<Array<HTMLInputElement | null>>([]);
  return (
    <div className="spatial-map__observed" data-testid="spatial-map-observed-views">
      <p className="spatial-map__observed-title">Observed location photographs</p>
      <p className="spatial-map__tip">
        Additional views must be real photos of the same place. Generated images do not count.
      </p>
      <div className="spatial-map__observed-row" data-testid="observed-master">
        <span className="spatial-map__badge">Observed</span>
        <span>Master{masterAssetId ? ` · ${masterAssetId.slice(0, 8)}…` : " · not chosen yet"}</span>
      </div>
      {EXTRA_SLOTS.map((slot) => {
        const current = views[slot - 1];
        return (
          <div key={slot} className="spatial-map__observed-row" data-testid={`observed-view-${slot}`}>
            <span className="spatial-map__badge">Observed</span>
            <span>Additional Observed View {slot}</span>
            {current ? (
              <span className="spatial-map__hint">{current.label || `${current.assetId.slice(0, 8)}…`}</span>
            ) : null}
            <button
              type="button"
              className="spatial-map__slot-action"
              disabled={disabled}
              onClick={() => onChooseLibrary(slot)}
              data-testid={`observed-view-${slot}-library`}
            >
              Choose from Library
            </button>
            <button
              type="button"
              className="spatial-map__slot-action"
              disabled={disabled}
              onClick={() => fileRefs.current[slot]?.click()}
              data-testid={`observed-view-${slot}-upload`}
            >
              Upload
            </button>
            {current && onClear ? (
              <button
                type="button"
                className="spatial-map__slot-action"
                disabled={disabled}
                onClick={() => onClear(slot)}
              >
                Remove
              </button>
            ) : null}
            <input
              ref={(el) => {
                fileRefs.current[slot] = el;
              }}
              type="file"
              accept="image/*"
              hidden
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) onUpload(slot, file);
                e.target.value = "";
              }}
            />
          </div>
        );
      })}
    </div>
  );
}
