import { useEffect, useState, type ReactNode } from "react";
import { MagiPreviewFitFrame } from "./MagiPreviewFitFrame";
import { MagiVideoStage } from "./MagiVideoStage";

export function MagiSplitView({
  originalSrc,
  processedSrc,
  processedKind,
  processedFilter,
  processedOpacity = 1,
  processedBlend,
  timeSeconds,
  playing,
  seekGeneration = 0,
  onClock,
  onEnded,
  onOriginalError,
  onProcessedError,
  processedOverlay,
  guidesVisible = false,
}: {
  originalSrc: string;
  processedSrc: string;
  processedKind: "video" | "image";
  processedFilter?: string;
  processedOpacity?: number;
  processedBlend?: ReactNode;
  timeSeconds: number | null;
  playing: boolean;
  seekGeneration?: number;
  onClock?: (seconds: number) => void;
  onEnded?: () => void;
  onOriginalError: () => void;
  onProcessedError: () => void;
  processedOverlay?: ReactNode;
  guidesVisible?: boolean;
}) {
  const [split, setSplit] = useState(50);
  const [dragging, setDragging] = useState(false);
  const [originalSize, setOriginalSize] = useState({ w: 0, h: 0 });
  const [processedSize, setProcessedSize] = useState({ w: 0, h: 0 });
  useEffect(() => {
    setOriginalSize({ w: 0, h: 0 });
  }, [originalSrc]);
  useEffect(() => {
    setProcessedSize({ w: 0, h: 0 });
  }, [processedSrc]);

  return (
    <div
      className="magi-split-view"
      data-testid="magi-split-view"
      onMouseMove={(event) => {
        if (!dragging) return;
        const box = event.currentTarget.getBoundingClientRect();
        const next = ((event.clientX - box.left) / Math.max(1, box.width)) * 100;
        setSplit(Math.max(20, Math.min(80, next)));
      }}
      onMouseUp={() => setDragging(false)}
      onMouseLeave={() => setDragging(false)}
    >
      <figure className="magi-split-pane" style={{ flexBasis: `${split}%` }} data-testid="magi-split-original" data-grade="raw">
        <MagiPreviewFitFrame mediaWidth={originalSize.w} mediaHeight={originalSize.h} guidesVisible={guidesVisible}>
          <MagiVideoStage
            src={originalSrc}
            timeSeconds={timeSeconds}
            playing={playing}
            muted
            clockRole="authority"
            seekGeneration={seekGeneration}
            onClock={onClock}
            onEnded={onEnded}
            onError={onOriginalError}
            onReadySize={(width, height) =>
              setOriginalSize((prev) => (prev.w === width && prev.h === height ? prev : { w: width, h: height }))
            }
          />
        </MagiPreviewFitFrame>
        <figcaption>Original</figcaption>
      </figure>
      <button
        type="button"
        className="magi-split-divider"
        data-testid="magi-split-divider"
        aria-label="Resize split"
        onMouseDown={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDoubleClick={() => setSplit(50)}
      />
      <figure
        className="magi-split-pane"
        style={{ flexBasis: `${100 - split}%` }}
        data-testid="magi-split-processed"
        data-grade="live"
        data-live-filter={processedFilter || ""}
      >
        <MagiPreviewFitFrame mediaWidth={processedSize.w} mediaHeight={processedSize.h} guidesVisible={guidesVisible}>
          {processedBlend ? (
            processedBlend
          ) : processedKind === "video" ? (
            <MagiVideoStage
              src={processedSrc}
              timeSeconds={timeSeconds}
              playing={playing}
              muted
              clockRole="follower"
              seekGeneration={seekGeneration}
              filter={processedFilter}
              opacity={processedOpacity}
              onError={onProcessedError}
              onReadySize={(width, height) =>
                setProcessedSize((prev) => (prev.w === width && prev.h === height ? prev : { w: width, h: height }))
              }
            />
          ) : (
            <img
              src={processedSrc}
              alt=""
              style={{ filter: processedFilter || "none", opacity: processedOpacity }}
              onError={onProcessedError}
              onLoad={(event) => {
                const image = event.currentTarget;
                if (image.naturalWidth > 0 && image.naturalHeight > 0) {
                  setProcessedSize({ w: image.naturalWidth, h: image.naturalHeight });
                }
              }}
            />
          )}
          {processedOverlay}
        </MagiPreviewFitFrame>
        <figcaption>MAGI</figcaption>
      </figure>
    </div>
  );
}
