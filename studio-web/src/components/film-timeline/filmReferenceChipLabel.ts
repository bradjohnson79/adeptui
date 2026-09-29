/** Single-grammar chip label for Film Timeline reference strip (@ # % * &). */
export function filmReferenceChipLabel(ref: {
  type?: string | null;
  tag?: string | null;
  label?: string | null;
}): string {
  const prefix =
    ref.type === "environment"
      ? "#"
      : ref.type === "prop"
        ? "%"
        : ref.type === "video"
          ? "*"
          : ref.type === "audio"
            ? "&"
            : "@";
  const raw = String(ref.tag || ref.label || "").trim();
  if (!raw) return ref.type || "Reference";
  // Canonical tag already includes a single grammar prefix. Collapse stacked @@ / ##.
  if (raw.startsWith(prefix) || /^[@#%*&~]/.test(raw)) {
    return raw.replace(/^([@#%*&~])+/, prefix);
  }
  return `${prefix}${raw}`;
}
