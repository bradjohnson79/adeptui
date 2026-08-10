import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import "./button.css";

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "tertiary"
  | "ghost"
  | "icon"
  | "danger"
  | "compact";

export type ButtonTone = "default" | "success" | "warning" | "error";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  tone?: ButtonTone;
  selected?: boolean;
  loading?: boolean;
  compact?: boolean;
  /** Required for icon-only buttons when children are not text. */
  "aria-label"?: string;
  children?: ReactNode;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "secondary",
    tone = "default",
    selected = false,
    loading = false,
    compact = false,
    className = "",
    disabled,
    children,
    type = "button",
    ...rest
  },
  ref
) {
  const resolvedVariant = variant === "compact" ? "secondary" : variant;
  const classes = [
    "ui-btn",
    `ui-btn--${resolvedVariant}`,
    compact || variant === "compact" ? "ui-btn--compact" : "",
    tone !== "default" ? `ui-btn--tone-${tone}` : "",
    selected ? "is-selected" : "",
    loading ? "is-loading" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      ref={ref}
      type={type}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      aria-pressed={selected || undefined}
      {...rest}
    >
      {loading ? <span className="ui-btn__spinner" aria-hidden /> : null}
      {children}
    </button>
  );
});

export const IconButton = forwardRef<HTMLButtonElement, ButtonProps>(function IconButton(
  { variant = "icon", children, "aria-label": ariaLabel, ...rest },
  ref
) {
  if (!ariaLabel && !rest.title) {
    console.warn("IconButton requires aria-label");
  }
  return (
    <Button
      ref={ref}
      variant={variant === "compact" ? "compact" : "icon"}
      aria-label={ariaLabel}
      {...rest}
    >
      {children}
    </Button>
  );
});
