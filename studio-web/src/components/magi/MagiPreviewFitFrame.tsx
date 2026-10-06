import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { mediaContainRect } from "../../workspace/mediaFit";
import { aspectFromDimensions } from "../../workspace/compositionGuides";
import { AdeptCompositionGuides } from "../shared/AdeptCompositionGuides";
import { MagiVideoStage } from "./MagiVideoStage";

/**
 * Fits media inside the MAGI Preview Monitor (contain / Fit).
 * Source pixels never grow the Viewer. Overlays should be children of the frame.
 * Guides fill this already-fitted composition rectangle (mode=fill).
 * Unknown dimensions fill the host with object-fit contain. They do not assume 16:9.
 */
export function MagiPreviewFitFrame({
  mediaWidth,
  mediaHeight,
  children,
  guidesVisible = false,
}: {
  mediaWidth?: number;
  mediaHeight?: number;
  children: ReactNode;
  guidesVisible?: boolean;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [box, setBox] = useState({ x: 0, y: 0, w: 0, h: 0, scale: 0 });
  const known = Boolean(mediaWidth && mediaHeight && mediaWidth > 0 && mediaHeight > 0);
  const srcW = known ? Number(mediaWidth) : 0;
  const srcH = known ? Number(mediaHeight) : 0;

  useLayoutEffect(() => {
    const el = hostRef.current;
    if (!el) return;
    const apply = () => {
      const r = el.getBoundingClientRect();
      setBox(mediaContainRect(r.width, r.height, srcW, srcH));
    };
    apply();
    const ro = new ResizeObserver(apply);
    ro.observe(el);
    window.addEventListener("resize", apply);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", apply);
    };
  }, [srcW, srcH]);

  return (
    <div
      ref={hostRef}
      className="magi-preview-fit-host"
      data-testid="magi-preview-fit-host"
      data-fit="contain"
    >
      <div
        className="magi-preview-fit-frame"
        data-testid="magi-preview-fit-frame"
        data-fit-scale={box.scale ? box.scale.toFixed(4) : "0"}
        data-source-w={srcW}
        data-source-h={srcH}
        data-frame-w={Math.round(box.w)}
        data-frame-h={Math.round(box.h)}
        style={
          known
            ? {
                left: box.x,
                top: box.y,
                width: box.w,
                height: box.h,
              }
            : {
                left: 0,
                top: 0,
                width: "100%",
                height: "100%",
              }
        }
      >
        {children}
        <AdeptCompositionGuides
          visible={guidesVisible && known}
          mode="fill"
          aspectRatio={aspectFromDimensions(srcW, srcH)}
        />
      </div>
    </div>
  );
}

export function MagiCompareFitMedia({
  kind,
  src,
  onError,
  timeSeconds = null,
  playing = false,
  seekGeneration = 0,
  clockRole = "follower",
  onClock,
  onEnded,
  guidesVisible = false,
  filter,
  opacity = 1,
  onReadySize,
}: {
  kind: "video" | "image";
  src: string;
  onError: () => void;
  timeSeconds?: number | null;
  playing?: boolean;
  seekGeneration?: number;
  clockRole?: "authority" | "follower";
  onClock?: (seconds: number) => void;
  onEnded?: () => void;
  guidesVisible?: boolean;
  filter?: string;
  opacity?: number;
  onReadySize?: (width: number, height: number) => void;
}) {
  const [size, setSize] = useState({ w: 0, h: 0 });
  useEffect(() => {
    setSize({ w: 0, h: 0 });
  }, [src]);
  return (
    <MagiPreviewFitFrame mediaWidth={size.w} mediaHeight={size.h} guidesVisible={guidesVisible}>
      {kind === "video" ? (
        <MagiVideoStage
          src={src}
          timeSeconds={timeSeconds}
          playing={playing}
          muted
          filter={filter}
          opacity={opacity}
          clockRole={clockRole}
          seekGeneration={seekGeneration}
          onClock={onClock}
          onEnded={onEnded}
          onError={onError}
          onReadySize={(width, height) => {
            setSize((prev) => (prev.w === width && prev.h === height ? prev : { w: width, h: height }));
            onReadySize?.(width, height);
          }}
        />
      ) : (
        <img
          src={src}
          alt=""
          style={{ ...(filter ? { filter } : {}), opacity }}
          onError={onError}
          onLoad={(event) => {
            const image = event.currentTarget;
            if (image.naturalWidth > 0 && image.naturalHeight > 0) {
              setSize({ w: image.naturalWidth, h: image.naturalHeight });
              onReadySize?.(image.naturalWidth, image.naturalHeight);
            }
          }}
        />
      )}
    </MagiPreviewFitFrame>
  );
}
