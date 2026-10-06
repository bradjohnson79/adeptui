import {
  TransportBatchEndIcon,
  TransportBatchStartIcon,
  TransportForward5Icon,
  TransportPauseIcon,
  TransportPlayIcon,
  TransportRewind5Icon,
  TransportSceneEndIcon,
  TransportSceneStartIcon,
} from "../timeline-master/previewTransportIcons";
import "../../styles/timeline-master/preview-fullscreen.css";
import type { MagiSequenceDocument } from "../../magiSequence/types";
import { magiSeekFrame, magiSkipFrame, magiTransportAt } from "./magiTransport";

/** Same control order, icons, and labels as the Timeline preview transport. */
export function MagiPreviewTransport({
  sequence,
  playing,
  onTogglePlay,
  onSeekFrame,
}: {
  sequence: MagiSequenceDocument | null;
  playing: boolean;
  onTogglePlay: () => void;
  onSeekFrame: (frame: number) => void;
}) {
  const clock = sequence ? magiTransportAt(sequence, sequence.playheadFrame) : null;
  const hasPicture = Boolean(clock?.hasPicture);
  const piece = clock?.piece ?? null;
  const playLabel = playing ? "Pause" : "Play";
  const magiSeek = (seconds: number) => {
    if (!sequence) return;
    onSeekFrame(magiSeekFrame(sequence, seconds));
  };
  return (
    <div className="film-preview-transport magi-preview-transport" data-testid="magi-preview-transport" role="toolbar" aria-label="Preview transport">
      <button type="button" className="preview-transport-btn" data-testid="magi-go-start" title="Beginning of Scene" aria-label="Beginning of Scene" disabled={!hasPicture} onClick={() => magiSeek(0)}>
        <TransportSceneStartIcon />
      </button>
      <button type="button" className="preview-transport-btn" data-testid="magi-clip-start" title="Start of Batch" aria-label="Start of Batch" disabled={!piece} onClick={() => piece && magiSeek(piece.start)}>
        <TransportBatchStartIcon />
      </button>
      <button type="button" className="preview-transport-btn" data-testid="magi-back-5" title="Back 5 seconds" aria-label="Back 5 seconds" disabled={!hasPicture} onClick={() => sequence && onSeekFrame(magiSkipFrame(sequence, sequence.playheadFrame, -5))}>
        <TransportRewind5Icon />
      </button>
      <button type="button" className="preview-transport-btn preview-transport-play" data-testid="magi-play" title={playLabel} aria-label={playLabel} aria-pressed={playing} disabled={!hasPicture} onClick={onTogglePlay}>
        {playing ? <TransportPauseIcon /> : <TransportPlayIcon />}
      </button>
      <button type="button" className="preview-transport-btn" data-testid="magi-forward-5" title="Forward 5 seconds" aria-label="Forward 5 seconds" disabled={!hasPicture} onClick={() => sequence && onSeekFrame(magiSkipFrame(sequence, sequence.playheadFrame, 5))}>
        <TransportForward5Icon />
      </button>
      <button type="button" className="preview-transport-btn" data-testid="magi-clip-end" title="End of Batch" aria-label="End of Batch" disabled={!piece} onClick={() => piece && magiSeek(piece.end)}>
        <TransportBatchEndIcon />
      </button>
      <button type="button" className="preview-transport-btn" data-testid="magi-go-end" title="End of Scene" aria-label="End of Scene" disabled={!hasPicture} onClick={() => clock && magiSeek(clock.bounds.sceneEnd)}>
        <TransportSceneEndIcon />
      </button>
    </div>
  );
}
