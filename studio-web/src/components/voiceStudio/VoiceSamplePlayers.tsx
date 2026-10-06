import { useEffect, useRef, useState } from "react";
import { Button } from "../ui";
import { approveReplacementNote } from "./defaultVoiceCopy";

export type VoiceSamplePlayerItem = {
  id: string;
  status: string;
  audioUrl?: string;
  assetId?: string;
  error?: string;
  voiceProfileId?: string;
  provider?: string;
  name?: string;
  modelId?: string;
  providerVoiceId?: string;
  createdAt?: string;
};

type Props = {
  samples: VoiceSamplePlayerItem[];
  characterName: string;
  approvedSampleId?: string;
  onApprove: (sample: VoiceSamplePlayerItem) => void;
  approveDisabled?: boolean;
  replacingApproved?: boolean;
};

export function formatAudioClock(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const whole = Math.floor(seconds);
  const minutes = Math.floor(whole / 60);
  const rest = whole % 60;
  return `${minutes}:${rest.toString().padStart(2, "0")}`;
}

export function VoiceSamplePlayers({
  samples,
  characterName,
  approvedSampleId = "",
  onApprove,
  approveDisabled,
  replacingApproved,
}: Props) {
  const audioRefs = useRef<Record<string, HTMLAudioElement | null>>({});
  const [playingId, setPlayingId] = useState("");
  const [times, setTimes] = useState<Record<string, { current: number; duration: number }>>({});

  useEffect(() => {
    return () => {
      Object.values(audioRefs.current).forEach((audio) => {
        if (!audio) return;
        audio.pause();
      });
    };
  }, []);

  const pauseOthers = (keepId: string) => {
    Object.entries(audioRefs.current).forEach(([id, audio]) => {
      if (!audio || id === keepId) return;
      audio.pause();
    });
  };

  const togglePlay = async (sample: VoiceSamplePlayerItem) => {
    const audio = audioRefs.current[sample.id];
    if (!audio || !sample.audioUrl) return;
    if (playingId === sample.id && !audio.paused) {
      audio.pause();
      setPlayingId("");
      return;
    }
    pauseOthers(sample.id);
    if (audio.ended) audio.currentTime = 0;
    try {
      await audio.play();
      setPlayingId(sample.id);
    } catch {
      setPlayingId("");
    }
  };

  if (!samples.length) return null;

  return (
    <div className="vip-section vip-sample-players" data-testid="vip-sample-players">
      <p className="muted vip-sample-players__note">
        Play each sample for {characterName || "this character"}, then approve the one that should be the current voice.
      </p>
      <div className="vip-sample-players__list">
        {samples.map((sample, index) => {
          const time = times[sample.id] || { current: 0, duration: 0 };
          const isApproved = Boolean(approvedSampleId) && sample.id === approvedSampleId;
          const canPlay = sample.status === "ready" && Boolean(sample.audioUrl);
          return (
            <div
              key={sample.id}
              className={"vip-sample-player" + (isApproved ? " is-approved" : "")}
              data-testid={"vs-sample-" + index}
            >
              <strong className="vip-sample-player__name">Sample {index + 1}</strong>
              <audio
                ref={(node) => {
                  audioRefs.current[sample.id] = node;
                }}
                src={sample.audioUrl}
                preload="metadata"
                data-testid={"vs-sample-audio-" + index}
                onLoadedMetadata={(event) => {
                  const audio = event.currentTarget;
                  setTimes((current) => ({
                    ...current,
                    [sample.id]: { current: audio.currentTime, duration: audio.duration || 0 },
                  }));
                }}
                onTimeUpdate={(event) => {
                  const audio = event.currentTarget;
                  setTimes((current) => ({
                    ...current,
                    [sample.id]: { current: audio.currentTime, duration: audio.duration || 0 },
                  }));
                }}
                onPlay={() => {
                  pauseOthers(sample.id);
                  setPlayingId(sample.id);
                }}
                onPause={() => {
                  setPlayingId((current) => (current === sample.id ? "" : current));
                }}
                onEnded={() => {
                  setPlayingId((current) => (current === sample.id ? "" : current));
                }}
              />
              <Button
                data-testid={"vs-sample-play-" + index}
                disabled={!canPlay}
                aria-label={playingId === sample.id ? `Pause sample ${index + 1}` : `Play sample ${index + 1}`}
                onClick={() => void togglePlay(sample)}
              >
                {playingId === sample.id ? "Pause" : "Play"}
              </Button>
              <label className="vip-sample-player__scrub">
                <span className="vip-sr-only">Seek sample {index + 1}</span>
                <input
                  type="range"
                  min={0}
                  max={Math.max(time.duration, 0.01)}
                  step={0.05}
                  value={time.current}
                  disabled={!canPlay}
                  data-testid={"vs-sample-scrub-" + index}
                  aria-label={`Seek sample ${index + 1}`}
                  onChange={(event) => {
                    const audio = audioRefs.current[sample.id];
                    const next = Number(event.target.value);
                    if (audio) audio.currentTime = next;
                    setTimes((current) => ({
                      ...current,
                      [sample.id]: { current: next, duration: time.duration },
                    }));
                  }}
                />
              </label>
              <span className="vip-sample-player__time" data-testid={"vs-sample-time-" + index}>
                {canPlay ? `${formatAudioClock(time.current)} / ${formatAudioClock(time.duration)}` : sample.error || sample.status}
              </span>
              <Button
                variant={isApproved ? "secondary" : "primary"}
                data-testid={"vs-sample-approve-" + index}
                disabled={isApproved || approveDisabled || !canPlay}
                aria-pressed={isApproved}
                aria-label={isApproved ? `Sample ${index + 1} approved` : `Approve sample ${index + 1}`}
                onClick={() => onApprove(sample)}
              >
                {isApproved ? "Approved ✓" : "Approve"}
              </Button>
            </div>
          );
        })}
      </div>
      {replacingApproved ? (
        <p className="muted" data-testid="vs-approve-replace-note">
          {approveReplacementNote(characterName)}
        </p>
      ) : null}
    </div>
  );
}
