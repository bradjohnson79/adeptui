import { expect, test } from "@playwright/test";

type RuntimeStatus = {
  ok?: boolean;
  providerId?: string;
  providerVersion?: string;
  installed?: boolean;
  ready?: boolean;
  availableOnDisk?: boolean;
  message?: string;
  mock?: boolean;
  language?: Record<string, unknown>;
  capabilityMetadata?: { language?: Record<string, unknown> };
};

type Capabilities = {
  ok?: boolean;
  providerId?: string;
  providerVersion?: string;
  status?: string;
  installed?: boolean;
  ready?: boolean;
  supportsLiveGeneration?: boolean;
  supportsEmotionVectors?: boolean;
  supportedEmotionVectors?: string[];
  directionModes?: string[];
  presetsAvailable?: number;
  message?: string;
  mock?: boolean;
  language?: Record<string, unknown>;
  capabilityMetadata?: { language?: Record<string, unknown> };
};

function languageMetadata(...sources: unknown[]): Record<string, unknown> | null {
  for (const source of sources) {
    if (!source || typeof source !== "object") continue;
    const body = source as {
      language?: Record<string, unknown>;
      capabilityMetadata?: { language?: Record<string, unknown> };
    };
    if (body.language && typeof body.language === "object") return body.language;
    if (body.capabilityMetadata?.language && typeof body.capabilityMetadata.language === "object") {
      return body.capabilityMetadata.language;
    }
  }
  return null;
}

test.describe("M4.10 Voice Performance API contract", () => {
  test("runtime and capabilities report IndexTTS2 readiness honestly", async ({ request }) => {
    const [runtimeResponse, capabilitiesResponse] = await Promise.all([
      request.get("/api/voice-performance/m410/runtime/status"),
      request.get("/api/voice-performance/m410/capabilities"),
    ]);

    expect(runtimeResponse.ok(), `runtime status failed: ${runtimeResponse.status()} ${await runtimeResponse.text()}`).toBeTruthy();
    expect(
      capabilitiesResponse.ok(),
      `capabilities failed: ${capabilitiesResponse.status()} ${await capabilitiesResponse.text()}`,
    ).toBeTruthy();

    const runtime = (await runtimeResponse.json()) as RuntimeStatus;
    const capabilities = (await capabilitiesResponse.json()) as Capabilities;

    expect(runtime.ok).toBeTruthy();
    expect(capabilities.ok).toBeTruthy();
    expect(runtime.mock).not.toBe(true);
    expect(capabilities.mock).not.toBe(true);

    expect(runtime.providerId).toBe("index-tts2-local");
    expect(capabilities.providerId).toBe("index-tts2-local");
    expect(capabilities.directionModes || []).toEqual(expect.arrayContaining(["codirector", "manual"]));
    expect(capabilities.supportedEmotionVectors || []).toEqual(
      expect.arrayContaining(["joy", "sadness", "anger", "fear", "surprise", "disgust", "contempt"]),
    );

    if (runtime.ready) {
      expect(capabilities.ready).toBe(true);
      expect(capabilities.supportsLiveGeneration).toBe(true);
      expect(capabilities.status).toBe("available");
    } else {
      expect(capabilities.supportsLiveGeneration).toBe(false);
      expect(capabilities.status).toBe("requires_setup");
    }

    const language = languageMetadata(capabilities, runtime);
    expect(language, "language honesty metadata must be surfaced to the API").toBeTruthy();
    expect(language?.accent).toBe("experimental");
    expect(language?.mixed_language ?? language?.mixedLanguage).toBe("not_recommended");
  });
});
