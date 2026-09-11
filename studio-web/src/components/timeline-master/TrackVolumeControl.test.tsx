import { describe, expect, it, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { TrackVolumeControl, stepVolumePercent } from "./TrackVolumeControl";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: { defaultValue?: string; [k: string]: unknown }) => {
      const def = options?.defaultValue;
      if (typeof def === "string") {
        return def.replace(/\{\{(\w+)\}\}/g, (_, name) => String(options?.[name] ?? ""));
      }
      return key;
    },
  }),
}));

describe("TrackVolumeControl static render", () => {
  it("renders the current percentage", () => {
    const html = renderToString(
      <TrackVolumeControl
        trackLabel="Music"
        volumePercent={65}
        muted={false}
        onChange={() => undefined}
        onToggleMute={() => undefined}
      />,
    );
    expect(html).toMatch(/65(?:<!-- -->)?%/);
  });

  it("percent button has aria-expanded, aria-haspopup and a descriptive aria-label", () => {
    const html = renderToString(
      <TrackVolumeControl
        trackLabel="Music"
        volumePercent={65}
        muted={false}
        onChange={() => undefined}
        onToggleMute={() => undefined}
      />,
    );
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain('aria-haspopup="dialog"');
    expect(html).toContain('aria-label="Music volume, 65 percent"');
  });

  it("mute button reports aria-pressed false and accessible name when unmuted", () => {
    const html = renderToString(
      <TrackVolumeControl
        trackLabel="Music"
        volumePercent={80}
        muted={false}
        onChange={() => undefined}
        onToggleMute={() => undefined}
      />,
    );
    expect(html).toContain('aria-pressed="false"');
    expect(html).toContain('aria-label="Mute Music"');
  });

  it("mute button reports aria-pressed true and accessible name when muted", () => {
    const html = renderToString(
      <TrackVolumeControl
        trackLabel="Music"
        volumePercent={80}
        muted={true}
        onChange={() => undefined}
        onToggleMute={() => undefined}
      />,
    );
    expect(html).toContain('aria-pressed="true"');
    expect(html).toContain('aria-label="Unmute Music"');
  });

  it("is disabled and shows a tooltip when the track has no clips", () => {
    const html = renderToString(
      <TrackVolumeControl
        trackLabel="Music"
        volumePercent={100}
        muted={false}
        disabled
        onChange={() => undefined}
        onToggleMute={() => undefined}
      />,
    );
    expect(html).toContain("disabled");
    expect(html).toContain("Add a clip to set Music volume");
  });
});

describe("stepVolumePercent", () => {
  it("steps by 1% for arrow keys", () => {
    expect(stepVolumePercent(65, false, "ArrowUp")).toBe(66);
    expect(stepVolumePercent(65, false, "ArrowRight")).toBe(66);
    expect(stepVolumePercent(65, false, "ArrowDown")).toBe(64);
    expect(stepVolumePercent(65, false, "ArrowLeft")).toBe(64);
  });

  it("steps by 5% when Shift is held", () => {
    expect(stepVolumePercent(65, true, "ArrowUp")).toBe(70);
    expect(stepVolumePercent(65, true, "ArrowRight")).toBe(70);
    expect(stepVolumePercent(65, true, "ArrowDown")).toBe(60);
    expect(stepVolumePercent(65, true, "ArrowLeft")).toBe(60);
  });

  it("clamps at 0 and 100", () => {
    expect(stepVolumePercent(2, false, "ArrowDown")).toBe(1);
    expect(stepVolumePercent(1, false, "ArrowDown")).toBe(0);
    expect(stepVolumePercent(0, false, "ArrowDown")).toBe(0);
    expect(stepVolumePercent(99, false, "ArrowUp")).toBe(100);
    expect(stepVolumePercent(100, false, "ArrowUp")).toBe(100);
    expect(stepVolumePercent(3, true, "ArrowDown")).toBe(0);
    expect(stepVolumePercent(98, true, "ArrowUp")).toBe(100);
  });
});
