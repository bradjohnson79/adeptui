import { useCallback, useEffect, useRef, useState } from "react";

export type SpeechState = "idle" | "listening" | "processing" | "unsupported" | "denied" | "error";

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

export function useSpeechToText(onTranscript: (text: string) => void) {
  const [state, setState] = useState<SpeechState>(() => (getRecognitionCtor() ? "idle" : "unsupported"));
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const onTranscriptRef = useRef(onTranscript);
  onTranscriptRef.current = onTranscript;

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
      recognitionRef.current = null;
    };
  }, []);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
    setState((prev) => (prev === "listening" ? "processing" : prev === "unsupported" ? prev : "idle"));
  }, []);

  const start = useCallback(() => {
    const Ctor = getRecognitionCtor();
    if (!Ctor) {
      setState("unsupported");
      setError("Speech recognition is not supported in this browser.");
      return;
    }
    setError(null);
    try {
      recognitionRef.current?.abort();
      const recognition = new Ctor();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = navigator.language || "en-US";
      recognition.onresult = (event) => {
        const last = event.results[event.results.length - 1];
        const transcript = last?.[0]?.transcript?.trim();
        if (transcript) onTranscriptRef.current(transcript);
      };
      recognition.onerror = (event) => {
        if (event.error === "not-allowed" || event.error === "service-not-allowed") {
          setState("denied");
          setError("Microphone permission was denied. Enable it in your browser settings to dictate.");
        } else if (event.error === "aborted") {
          setState("idle");
        } else {
          setState("error");
          setError(`Speech recognition error: ${event.error}`);
        }
      };
      recognition.onend = () => {
        setState((prev) => (prev === "denied" || prev === "unsupported" ? prev : "idle"));
      };
      recognitionRef.current = recognition;
      recognition.start();
      setState("listening");
    } catch (err) {
      setState("error");
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  const toggle = useCallback(() => {
    if (state === "listening") stop();
    else if (state !== "unsupported") start();
  }, [start, state, stop]);

  return { state, error, start, stop, toggle };
}
