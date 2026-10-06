import { useEffect, useRef, useState } from "react";
import { Button } from "../ui";
import { formatAudioClock } from "./VoiceSamplePlayers";

type Props = {
  audioUrl: string;
  label?: string;
  testId?: string;
};

export function ApprovedVoicePlayer({ audioUrl, label = "approved voice", testId = "vip-approved-audio" }: Props) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState({ current: 0, duration: 0 });

  useEffect(() => {
    return () => {
      audioRef.current?.pause();
    };
  }, []);

  useEffect(() => {
    setPlaying(false);
    setTime({ current: 0, duration: 0 });
  }, [audioUrl]);

  const togglePlay = async () => {
    const audio = audioRef.current;
    if (!audio || !audioUrl) return;
    if (playing && !audio.paused) {
      audio.pause();
      setPlaying(false);
      return;
    }
    if (audio.ended) audio.currentTime = 0;
    try {
      await audio.play();
      setPlaying(true);
    } catch {
      setPlaying(false);
    }
  };

  return (
    <div className="vip-sample-player vip-approved-player" data-testid="vip-approved-player">
      <audio
        ref={audioRef}
        src={audioUrl}
        preload="metadata"
        data-testid={testId}
        onLoadedMetadata={(event) => {
          const audio = event.currentTarget;
          setTime({ current: audio.currentTime, duration: audio.duration || 0 });
        }}
        onTimeUpdate={(event) => {
          const audio = event.currentTarget;
          setTime({ current: audio.currentTime, duration: audio.duration || 0 });
        }}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
      />
      <Button
        data-testid="vip-approved-play"
        aria-label={playing ? `Pause ${label}` : `Play ${label}`}
        onClick={() => void togglePlay()}
      >
        {playing ? "Pause" : "Play"}
      </Button>
      <label className="vip-sample-player__scrub">
        <span className="vip-sr-only">Seek {label}</span>
        <input
          type="range"
          min={0}
          max={Math.max(time.duration, 0.01)}
          step={0.05}
          value={time.current}
          data-testid="vip-approved-scrub"
          aria-label={`Seek ${label}`}
          onChange={(event) => {
            const next = Number(event.target.value);
            if (audioRef.current) audioRef.current.currentTime = next;
            setTime((current) => ({ ...current, current: next }));
          }}
        />
      </label>
      <span className="vip-sample-player__time" data-testid="vip-approved-time">
        {`${formatAudioClock(time.current)} / ${formatAudioClock(time.duration)}`}
      </span>
    </div>
  );
}
