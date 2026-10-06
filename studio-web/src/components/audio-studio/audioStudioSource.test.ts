import { describe, expect, it } from "vitest";
import { audioTabFromSearch, creatorRuntimeName, sourceStatusFromProviders } from "./audioStudioSource";

describe("Audio Studio source truth", () => {
  it("uses creator language for local runtimes", () => {
    expect(creatorRuntimeName("ACE-Step")).toBe("Music Engine");
    expect(creatorRuntimeName("MMAudio")).toBe("Sound Engine");
  });

  it("marks GPU-ready ACE-Step as a ready Music Engine", () => {
    const status = sourceStatusFromProviders("music", {
      recommendation: { mode: "local", runtime: "ACE-Step", cuda: true },
      local: { "ACE-Step": { ready: true, cuda: true } },
    });
    expect(status.ready).toBe(true);
    expect(status.label).toBe("Music Engine");
  });

  it("treats an empty providers payload as checking, not unavailable", () => {
    const status = sourceStatusFromProviders("music", {});
    expect(status.ready).toBe(false);
    expect(status.checking).toBe(true);
    expect(status.mode).toBe("checking");
    expect(status.label).toBe("Music Engine");
  });

  it("keeps GPU-ready ACE-Step ready even when the adapter is sandbox-hosted", () => {
    const status = sourceStatusFromProviders("music", {
      recommendation: { mode: "local", runtime: "ACE-Step", cuda: true },
      local: { "ACE-Step": { ready: true, cuda: true, sandboxOnly: true } },
    });
    expect(status.ready).toBe(true);
    expect(status.label).toBe("Music Engine");
  });

  it("does not treat a missing runtime as ready", () => {
    const status = sourceStatusFromProviders("sfx", {
      recommendation: { mode: "unavailable", runtime: "MMAudio", reason: "Sound Engine is not ready yet." },
      local: { MMAudio: { ready: false } },
    });
    expect(status.ready).toBe(false);
  });

  it("does not mark Sound Engine ready from a Music Engine recommendation", () => {
    const status = sourceStatusFromProviders("sfx", {
      recommendation: { mode: "local", runtime: "ACE-Step", cuda: true },
      local: {
        "ACE-Step": { ready: true, cuda: true },
        MMAudio: { ready: false, cuda: false },
      },
    });
    expect(status.ready).toBe(false);
    expect(status.label).toBe("Sound Engine");
  });

  it("reads audioTab from the URL without inventing a second authority", () => {
    expect(audioTabFromSearch("?workspace=audiostudio&audioTab=ambience")).toBe("ambience");
    expect(audioTabFromSearch("?workspace=audiostudio")).toBe("music");
  });
});
