import { MagiVideoStage } from "./MagiVideoStage";
import { cutLayerPresentation } from "../../magiSequence/transitions";

type CutLayer = {
  clipId: string;
  src: string;
  kind: "video" | "image";
  timeSeconds: number;
};

/** Live picture blend. The playhead clip keeps the clock. No render is started. */
export function MagiCutPreview({
  transition,
  progress,
  outgoing,
  incoming,
  playheadClipId,
  playing,
  muted,
  filter,
  seekGeneration,
  driveClock = true,
  onClock,
  onEnded,
  onError,
  onReadySize,
}: {
  transition: "dissolve" | "fade" | "wipe";
  progress: number;
  outgoing: CutLayer;
  incoming: CutLayer;
  playheadClipId: string | null;
  playing: boolean;
  muted: boolean;
  filter?: string;
  seekGeneration: number;
  /** Split and Compare already have a clock. Only the Viewer blend drives it. */
  driveClock?: boolean;
  onClock: (seconds: number) => void;
  onEnded: () => void;
  onError: (assetClipId: string) => void;
  onReadySize: (width: number, height: number) => void;
}) {
  const look = cutLayerPresentation(transition, progress);
  const layers = [
    { role: "outgoing" as const, layer: outgoing, opacity: look.outgoingOpacity, clipPath: undefined as string | undefined },
    { role: "incoming" as const, layer: incoming, opacity: look.incomingOpacity, clipPath: look.incomingClipPath },
  ];
  return (
    <div
      className="magi-cut-blend"
      data-testid="magi-cut-blend"
      data-transition={transition}
      data-progress={progress.toFixed(3)}
    >
      {layers.map(({ role, layer, opacity, clipPath }) => {
        const authority = driveClock && layer.clipId === playheadClipId;
        return (
          <div
            key={role}
            className={`magi-cut-blend__layer magi-cut-blend__layer--${role}`}
            data-testid={`magi-cut-${role}`}
            data-opacity={opacity.toFixed(3)}
            style={{ opacity, clipPath }}
          >
            {layer.kind === "image" ? (
              <img
                src={layer.src}
                alt=""
                style={filter ? { filter } : undefined}
                onError={() => onError(layer.clipId)}
                onLoad={(event) => {
                  const image = event.currentTarget;
                  if (image.naturalWidth > 0 && image.naturalHeight > 0) {
                    onReadySize(image.naturalWidth, image.naturalHeight);
                  }
                }}
              />
            ) : (
              <MagiVideoStage
                src={layer.src}
                timeSeconds={layer.timeSeconds}
                playing={playing && authority}
                muted={!authority || muted}
                filter={filter}
                clockRole={authority ? "authority" : "follower"}
                seekGeneration={seekGeneration}
                onClock={authority ? onClock : undefined}
                onEnded={authority ? onEnded : undefined}
                onError={() => onError(layer.clipId)}
                onReadySize={onReadySize}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
