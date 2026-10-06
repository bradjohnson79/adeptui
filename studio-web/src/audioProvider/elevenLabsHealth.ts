import { api } from "../api";
import type { ElevenLabsHealth } from "./types";

/**
 * Direct ElevenLabs capability. The API returns status only, never the key.
 */
export async function probeElevenLabsHealth(): Promise<ElevenLabsHealth> {
  const unavailable: ElevenLabsHealth = {
    configured: false,
    connectionStatus: "unavailable",
    message: "ElevenLabs API key not configured.",
    displayName: "ElevenLabs API",
  };
  try {
    const res = await (api as any).elevenLabsAvailability();
    const status = String(res?.status || res?.connectionStatus || "unavailable");
    const configured = status === "available" || status === "configured";
    const message =
      status === "invalid"
        ? "ElevenLabs credentials are not valid."
        : status === "unavailable"
          ? "ElevenLabs API key not configured."
          : String(res?.message || (configured ? "ElevenLabs API is available." : unavailable.message));
    return {
      configured,
      connectionStatus: status,
      message,
      displayName: "ElevenLabs API",
    };
  } catch {
    return unavailable;
  }
}
