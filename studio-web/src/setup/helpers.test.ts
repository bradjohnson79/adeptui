import { describe, expect, it } from "vitest";
import { overallStatus, summarizeComponents } from "./helpers";
import type { SetupComponentStatus } from "./types";

function row(
  id: string,
  required: boolean,
  status: SetupComponentStatus["status"],
): SetupComponentStatus {
  return {
    id,
    component_id: id,
    name: id,
    required,
    status,
    category: "Core",
  } as SetupComponentStatus;
}

describe("setup summary aggregation", () => {
  it("counts required gaps separately from optional gaps", () => {
    const counts = summarizeComponents([
      row("comfyui", true, "ready"),
      row("ollama", true, "ready"),
      row("wavespeed_key", false, "not_installed"),
      row("internvideo3_8b", false, "not_installed"),
      row("optional_broken", false, "error"),
    ]);
    expect(counts.ready).toBe(2);
    expect(counts.not_installed).toBe(0);
    expect(counts.needs_attention).toBe(0);
    expect(counts.required_ready).toBe(2);
    expect(counts.optional_not_installed).toBe(2);
    expect(counts.optional_needs_attention).toBe(1);
    expect(overallStatus([
      row("comfyui", true, "ready"),
      row("wavespeed_key", false, "not_installed"),
    ])).toBe("ready");
  });
});
