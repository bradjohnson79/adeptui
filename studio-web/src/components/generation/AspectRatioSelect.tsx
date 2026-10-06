import { ASPECT_PRESETS } from "../../workspacePrefs";

/**
 * Creator-facing aspect-ratio dropdown. Uses the shared `ASPECT_PRESETS` list
 * (1:1, 4:3, 3:2, 16:10, 16:9, 18:9, 21:9, 9:16, 2.39:1, custom) so every
 * generation surface (1 Frame, 3 Frame, Text2Video) offers the same ratios.
 */
export function AspectRatioSelect({
  id,
  value,
  onChange,
  disabled,
}: {
  id: string;
  value: string;
  onChange: (aspect: string) => void;
  disabled?: boolean;
}) {
  return (
    <select
      id={id}
      data-testid={id}
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
    >
      {ASPECT_PRESETS.map((a) => (
        <option key={a} value={a}>
          {a}
        </option>
      ))}
    </select>
  );
}
