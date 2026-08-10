import { useCallback, useEffect, useRef, useState } from "react";

export type SpeechState =
  | "idle"
  | "permission"
  | "listening"
  | "processing"
  | "ready"
  | "unsupported"
  | "denied"
  | "unavailable"
  | "error"
  | "cancelled";

type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
};

type SpeechRecognitionEventLike = {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
};

function getRecognitionCtor(): (new () => SpeechRecognitionLike) | null {
  const w = window as Window & {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

function creatorErrorMessage(code: string): string {
  switch (code) {
    case "not-allowed":
    case "service-not-allowed":
      return "Microphone permission was denied. Enable it in your browser settings and try again.";
    case "audio-capture":
      return "No microphone was detected.";
    case "network":
      return "Speech could not be transcribed because the speech service is unreachable. You can retry or type your message.";
    case "no-speech":
      return "No speech was detected. Try again or type your message.";
    case "aborted":
      return "";
    default:
      return "Speech could not be transcribed. You can retry or type your message.";
  }
}

export function useSpeechToText(onTranscript: (text: string) => void) {
  const [state, setState] = useState<SpeechState>(() => (getRecognitionCtor() ? "idle" : "unsupported"));
  const [error, setError] = useState<string | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const onTranscriptRef = useRef(onTranscript);
  const cancelledRef = useRef(false);
  const gotResultRef = useRef(false);
  const timerRef = useRef<number | null>(null);
  onTranscriptRef.current = onTranscript;

  const clearTimer = useCallback(() => {
    if (timerRef.current != null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      cancelledRef.current = true;
      clearTimer();
      recognitionRef.current?.abort();
      recognitionRef.current = null;
    };
  }, [clearTimer]);

  const stop = useCallback(() => {
    cancelledRef.current = false;
    setState((prev) => (prev === "listening" || prev === "permission" ? "processing" : prev));
    recognitionRef.current?.stop();
    clearTimer();
  }, [clearTimer]);

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    clearTimer();
    setElapsedMs(0);
    setError(null);
    setState("cancelled");
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    window.setTimeout(() => {
      setState((prev) => (prev === "cancelled" ? "idle" : prev));
    }, 0);
  }, [clearTimer]);

  const start = useCallback(() => {
    const Ctor = getRecognitionCtor();
    if (!Ctor) {
      setState("unsupported");
      setError("Speech recognition is not supported in this browser. You can type your message instead.");
      return;
    }
    cancelledRef.current = false;
    gotResultRef.current = false;
    setError(null);
    setElapsedMs(0);
    setState("permission");
    try {
      recognitionRef.current?.abort();
      const recognition = new Ctor();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = navigator.language || "en-US";
      recognition.onresult = (event) => {
        if (cancelledRef.current) return;
        const last = event.results[event.results.length - 1];
        const transcript = last?.[0]?.transcript?.trim();
        if (transcript) {
          gotResultRef.current = true;
          onTranscriptRef.current(transcript);
          setState("ready");
        }
      };
      recognition.onerror = (event) => {
        if (cancelledRef.current || event.error === "aborted") {
          setState((prev) => (prev === "cancelled" ? prev : "idle"));
          return;
        }
        const message = creatorErrorMessage(event.error);
        if (event.error === "not-allowed" || event.error === "service-not-allowed") {
          setState("denied");
        } else if (event.error === "audio-capture") {
          setState("unavailable");
        } else {
          setState("error");
        }
        setError(message || null);
        clearTimer();
      };
      recognition.onend = () => {
        clearTimer();
        setState((prev) => {
          if (prev === "denied" || prev === "unsupported" || prev === "unavailable" || prev === "cancelled") {
            return prev;
          }
          if (gotResultRef.current || prev === "ready") return "idle";
          if (prev === "processing" || prev === "listening") return "idle";
          return "idle";
        });
      };
      recognitionRef.current = recognition;
      recognition.start();
      setState("listening");
      const startedAt = Date.now();
      clearTimer();
      timerRef.current = window.setInterval(() => {
        setElapsedMs(Date.now() - startedAt);
      }, 250);
    } catch (err) {
      clearTimer();
      const message = err instanceof Error ? err.message : String(err);
      if (/permission|not allowed/i.test(message)) {
        setState("denied");
        setError("Microphone permission was denied. Enable it in your browser settings and try again.");
      } else if (/device|audio|microphone/i.test(message)) {
        setState("unavailable");
        setError("No microphone was detected.");
      } else {
        setState("error");
        setError("Speech could not be transcribed. You can retry or type your message.");
      }
    }
  }, [clearTimer]);

  const toggle = useCallback(() => {
    if (state === "listening" || state === "permission") stop();
    else if (state !== "unsupported") start();
  }, [start, state, stop]);

  return { state, error, elapsedMs, start, stop, cancel, toggle };
}
