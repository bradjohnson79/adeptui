/**
 * AdeptSelect — Themed dropdown wrapper for the Adept UI design system.
 *
 * Uses the native <select> element with CSS custom properties for dark popup
 * styling where the browser supports it (color-scheme: dark, accent-color).
 * Falls back to the shared .adept-select CSS class for consistent styling.
 *
 * For complex pickers (searchable, grouped), use SearchableGroupedSelect instead.
 */
import { type SelectHTMLAttributes } from "react";

type AdeptSelectOption = {
  value: string;
  label: string;
  disabled?: boolean;
};

type AdeptSelectGroup = {
  label: string;
  options: AdeptSelectOption[];
};

type Props = Omit<SelectHTMLAttributes<HTMLSelectElement>, "children"> & {
  options?: AdeptSelectOption[];
  groups?: AdeptSelectGroup[];
  placeholder?: string;
  className?: string;
};

export function AdeptSelect({
  options,
  groups,
  placeholder = "Select...",
  className = "",
  value,
  onChange,
  disabled,
  ...rest
}: Props) {
  return (
    <select
      className={["adept-select", className].filter(Boolean).join(" ")}
      value={value}
      onChange={onChange}
      disabled={disabled}
      {...rest}
    >
      {placeholder ? (
        <option value="" disabled>
          {placeholder}
        </option>
      ) : null}
      {groups
        ? groups.map((group) => (
            <optgroup key={group.label} label={group.label}>
              {group.options.map((opt) => (
                <option key={opt.value} value={opt.value} disabled={opt.disabled}>
                  {opt.label}
                </option>
              ))}
            </optgroup>
          ))
        : options?.map((opt) => (
            <option key={opt.value} value={opt.value} disabled={opt.disabled}>
              {opt.label}
            </option>
          ))}
    </select>
  );
}
