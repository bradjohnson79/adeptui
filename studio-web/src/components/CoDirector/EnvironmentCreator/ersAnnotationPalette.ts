/** Default ERS Edit/Inpaint annotation colors. Order is the toolbar order. */

export const ERS_ANNOTATION_COLORS = [
  { name: "White", value: "#ffffff" },
  { name: "Red", value: "#ef4444" },
  { name: "Orange", value: "#f97316" },
  { name: "Yellow", value: "#eab308" },
  { name: "Green", value: "#22c55e" },
  { name: "Aqua", value: "#22d3ee" },
  { name: "Blue", value: "#3b82f6" },
  { name: "Purple", value: "#a855f7" },
  { name: "Gray", value: "#9ca3af" },
  { name: "Black", value: "#000000" },
] as const;

export type DrawColor = (typeof ERS_ANNOTATION_COLORS)[number]["value"];

export const ERS_ANNOTATION_COLOR_VALUES: readonly DrawColor[] = ERS_ANNOTATION_COLORS.map(
  (swatch) => swatch.value,
);

function paletteColor(name: (typeof ERS_ANNOTATION_COLORS)[number]["name"]): DrawColor {
  const swatch = ERS_ANNOTATION_COLORS.find((item) => item.name === name);
  if (!swatch) throw new Error(`Missing ERS annotation color ${name}`);
  return swatch.value;
}

/** Fixed legend defaults. Drawing colors stay a separate choice. */
export const ERS_LEGEND_CHARACTER_COLORS: readonly DrawColor[] = [
  paletteColor("Red"),
  paletteColor("Orange"),
  paletteColor("Yellow"),
  paletteColor("Green"),
];

export const ERS_LEGEND_PROP_COLORS: readonly DrawColor[] = [
  paletteColor("Aqua"),
  paletteColor("Blue"),
  paletteColor("Purple"),
  paletteColor("Gray"),
];
