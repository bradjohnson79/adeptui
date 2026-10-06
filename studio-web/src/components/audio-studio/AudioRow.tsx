import { useEffect, useRef, useState } from "react";
import { Button } from "../ui";
import { formatAudioClock } from "../voiceStudio/VoiceSamplePlayers";

const PLAY_EVENT = "adept:audio-row-play";

type Props = {
  audioUrl?: string;
  label: string;
  testId?: string;
};

export function AudioRow({ audioUrl, label, testId = "audio-row" }: Props) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState({ current: 0, duration: 0 });

  useEffect(() => {
    const onPlay = (event: Event) => {
      const other = (event as CustomEvent<{ id?: string }>).detail?.id;
      if (other && other !== audioUrl) {
        audioRef.current?.pause();
        setPlaying(false);
      }
    };
    window.addEventListener(PLAY_EVENT, onPlay as EventListener);
    return () => {
      window.removeEventListener(PLAY_EVENT, onPlay as EventListener);
      audioRef.current?.pause();
    };
  }, [audioUrl]);

  useEffect(() => {
    setPlaying(false);
    setTime({ current: 0, duration: 0 });
  }, [audioUrl]);

  if (!audioUrl) {
    return <p className="muted audio-row__empty">No playable audio yet.</p>;
  }

  const togglePlay = async () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing && !audio.paused) {
      audio.pause();
      setPlaying(false);
      return;
    }
    window.dispatchEvent(new CustomEvent(PLAY_EVENT, { detail: { id: audioUrl } }));
    if (audio.ended) audio.currentTime = 0;
    try {
      await audio.play();
      setPlaying(true);
    } catch {
      setPlaying(false);
    }
  };

  return (
    <div className="audio-row" data-testid={testId}>
      <audio
        ref={audioRef}
        src={audioUrl}
        preload="metadata"
        onLoadedMetadata={(event) => {
          const node = event.currentTarget;
          setTime({ current: node.currentTime, duration: node.duration || 0 });
        }}
        onTimeUpdate={(event) => {
          const node = event.currentTarget;
          setTime({ current: node.currentTime, duration: node.duration || 0 });
        }}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
      />
      <Button
        type="button"
        data-testid={`${testId}-play`}
        aria-label={playing ? `Pause ${label}` : `Play ${label}`}
        onClick={() => void togglePlay()}
      >
        {playing ? "Pause" : "Play"}
      </Button>
      <label className="audio-row__scrub">
        <span className="audio-sr-only">Seek {label}</span>
        <input
          type="range"
          min={0}
          max={Math.max(time.duration, 0.01)}
          step={0.05}
          value={time.current}
          data-testid={`${testId}-scrub`}
          aria-label={`Seek ${label}`}
          onChange={(event) => {
            const next = Number(event.target.value);
            if (audioRef.current) audioRef.current.currentTime = next;
            setTime((current) => ({ ...current, current: next }));
          }}
        />
      </label>
      <span className="audio-row__clock" data-testid={`${testId}-clock`}>
        {formatAudioClock(time.current)} / {formatAudioClock(time.duration)}
      </span>
    </div>
  );
}
