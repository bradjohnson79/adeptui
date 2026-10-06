import { useEffect, useState } from "react";
import {
  getAudioStudioProvider,
  setAudioStudioProvider,
  subscribeAudioStudioProvider,
  bindAudioStudioProviderStorage,
} from "./audioStudioProviderStore";
import {
  getVoiceStudioProvider,
  setVoiceStudioProvider,
  subscribeVoiceStudioProvider,
} from "./voiceStudioProviderStore";
import { probeElevenLabsHealth } from "./elevenLabsHealth";
import type { AdeptAudioProviderSource, ElevenLabsHealth } from "./types";

/** Audio Studio may still choose Local | API — ElevenLabs. */
export function useAudioStudioProviderSource() {
  const [source, setSource] = useState<AdeptAudioProviderSource>(() => getAudioStudioProvider());
  const [health, setHealth] = useState<ElevenLabsHealth | null>(null);
  const [healthBusy, setHealthBusy] = useState(false);

  useEffect(() => {
    const unsub = subscribeAudioStudioProvider(setSource);
    const unbind = bindAudioStudioProviderStorage();
    return () => { unsub(); unbind(); };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setHealthBusy(true);
    void probeElevenLabsHealth().then((next) => {
      if (!cancelled) setHealth(next);
    }).finally(() => { if (!cancelled) setHealthBusy(false); });
    return () => { cancelled = true; };
  }, [source]);

  return {
    source,
    setSource: setAudioStudioProvider,
    health,
    healthBusy,
    refreshHealth: async () => {
      setHealthBusy(true);
      try {
        const next = await probeElevenLabsHealth();
        setHealth(next);
        return next;
      } finally {
        setHealthBusy(false);
      }
    },
  };
}

/** Voice Studio chooses Local or ElevenLabs. Local stays selected until the creator changes it. */
export function useVoiceStudioProviderSource() {
  const [source, setSource] = useState<AdeptAudioProviderSource>(() => getVoiceStudioProvider());
  const [health, setHealth] = useState<ElevenLabsHealth | null>(null);
  const [healthBusy, setHealthBusy] = useState(false);

  useEffect(() => subscribeVoiceStudioProvider(setSource), []);

  useEffect(() => {
    let cancelled = false;
    setHealthBusy(true);
    void probeElevenLabsHealth().then((next) => {
      if (!cancelled) setHealth(next);
    }).finally(() => { if (!cancelled) setHealthBusy(false); });
    return () => { cancelled = true; };
  }, [source]);

  return {
    source,
    setSource: setVoiceStudioProvider,
    health,
    healthBusy,
    refreshHealth: async () => {
      setHealthBusy(true);
      try {
        const next = await probeElevenLabsHealth();
        setHealth(next);
        return next;
      } finally {
        setHealthBusy(false);
      }
    },
  };
}
