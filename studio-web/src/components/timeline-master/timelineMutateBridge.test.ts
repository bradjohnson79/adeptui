import { describe, expect, it } from "vitest";
import { overlayLiveTimeline, type TimelineBoardView, type PromptSegment } from "../DirectorTracks";
import { applyShellPromptSnapshot, bindShellTimelineSnapshot } from "./timelineMutateBridge";

function clip(partial: Partial<PromptSegment> & Pick<PromptSegment, "id">): PromptSegment {
  return {
    id: partial.id,
    start: partial.start ?? 0,
    length: partial.length ?? 5,
    text: partial.text ?? "",
    reference_binding_ids: partial.reference_binding_ids ?? [],
    reference_name_bindings: partial.reference_name_bindings ?? [],
    weight: partial.weight ?? 1,
  } as PromptSegment;
}

function timeline(segments: PromptSegment[]): TimelineBoardView {
  return { promptSegments: segments } as TimelineBoardView;
}

describe("shared Timed Prompt snapshot", () => {
  it("applyShellPromptSnapshot is a no-op — Master is the Timed Prompt store", () => {
    const memory = timeline([
      clip({
        id: "ps1",
        text: "old",
        reference_name_bindings: [
          { binding_id: "ers", prompt_name: "Venture corridor", type: "environment", tag: "#VentureCorridorScene" },
        ],
      }),
    ]);
    const snapshot = timeline([
      clip({
        id: "ps1",
        text: "Korri and Anadriya walk through the Venture corridor.",
        reference_binding_ids: ["ers"],
        reference_name_bindings: [
          { binding_id: "ers", prompt_name: "the corridor", type: "environment", tag: "#VentureCorridorScene" },
        ],
      }),
    ]);
    const next = applyShellPromptSnapshot(memory, snapshot);
    expect(next).toBe(memory);
    expect(next.promptSegments[0].text).toBe("old");
  });

  it("does not let stale track memory overwrite saved name bindings on GET", () => {
    const live = timeline([
      clip({
        id: "ps1",
        reference_binding_ids: ["ers"],
        reference_name_bindings: [
          { binding_id: "ers", prompt_name: "Venture corridor", type: "environment", tag: "#VentureCorridorScene" },
        ],
      }),
    ]);
    const memory = timeline([
      clip({
        id: "ps1",
        reference_binding_ids: ["ers"],
        reference_name_bindings: [
          { binding_id: "ers", prompt_name: "Venture corridor", type: "environment", tag: "#VentureCorridorScene" },
        ],
      }),
    ]);
    const snapshot = timeline([
      clip({
        id: "ps1",
        reference_binding_ids: ["ers"],
        reference_name_bindings: [
          { binding_id: "ers", prompt_name: "the corridor", type: "environment", tag: "#VentureCorridorScene" },
        ],
      }),
    ]);
    bindShellTimelineSnapshot(snapshot);
    const merged = overlayLiveTimeline(live, memory);
    expect(merged.promptSegments[0].reference_name_bindings?.[0]?.prompt_name).toBe("the corridor");
    bindShellTimelineSnapshot(null);
  });

  it("does not let empty track memory wipe saved Timed Prompt text on GET", () => {
    const live = timeline([
      clip({
        id: "ps1",
        text: "Korri and Anadriya walk through the Venture corridor.",
      }),
    ]);
    const memory = timeline([clip({ id: "ps1", text: "" })]);
    const snapshot = timeline([
      clip({
        id: "ps1",
        text: "",
      }),
    ]);
    bindShellTimelineSnapshot(snapshot);
    const merged = overlayLiveTimeline(live, memory);
    expect(merged.promptSegments[0].text).toBe("Korri and Anadriya walk through the Venture corridor.");
    bindShellTimelineSnapshot(null);
  });

  it("does not resurrect cleared Timed Prompt text from track memory", () => {
    const live = timeline([clip({ id: "ps1", text: "" })]);
    const memory = timeline([clip({ id: "ps1", text: "stale draft" })]);
    bindShellTimelineSnapshot(timeline([clip({ id: "ps1", text: "" })]));
    const merged = overlayLiveTimeline(live, memory);
    expect(merged.promptSegments[0].text).toBe("");
    bindShellTimelineSnapshot(null);
  });
});
