import type { AnchorHTMLAttributes, ButtonHTMLAttributes, HTMLAttributes } from "react";
import { STATUS_KIND_LABELS, type StatusKind, mapStatusTone, statusToneClass, type StatusTone } from "../../status";
import "./status.css";

type CommonProps = {
  kind: StatusKind;
  label?: string;
  title?: string;
  compact?: boolean;
  tone?: StatusTone;
  className?: string;
  "data-testid"?: string;
};

export type StatusBadgeProps = CommonProps &
  (
    | ({ href: string; onClick?: never } & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href" | "title" | "className">)
    | ({ onClick: () => void; href?: never } & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onClick" | "title" | "type" | "className">)
    | ({ href?: undefined; onClick?: undefined } & Omit<HTMLAttributes<HTMLSpanElement>, "title" | "className">)
  );

const legacyTone: Record<StatusTone, string> = {
  positive: "ok",
  warning: "warn",
  danger: "bad",
  neutral: "",
  info: "",
  muted: "",
};

function badgeClassName(resolvedTone: StatusTone, compact: boolean, className: string, interactive: boolean) {
  return [
    "status-badge",
    "ds-status-badge",
    statusToneClass(resolvedTone),
    legacyTone[resolvedTone],
    compact ? "ds-status-badge--compact" : "",
    interactive ? "ds-status-badge--interactive" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");
}

export function StatusBadge(props: StatusBadgeProps) {
  const {
    kind,
    label,
    title,
    compact = false,
    tone,
    className = "",
    href,
    onClick,
    ...rest
  } = props as StatusBadgeProps & { href?: string; onClick?: () => void };
  const resolvedTone = tone ?? mapStatusTone(kind);
  const text = label ?? STATUS_KIND_LABELS[kind];
  const tip = title ?? text;
  const classes = badgeClassName(resolvedTone, compact, className, Boolean(href || onClick));

  if (href) {
    const { ["data-testid"]: testId, ...anchorRest } = rest as AnchorHTMLAttributes<HTMLAnchorElement> & {
      "data-testid"?: string;
    };
    return (
      <a
        {...anchorRest}
        href={href}
        title={tip}
        data-testid={testId}
        className={classes}
      >
        {text}
      </a>
    );
  }

  if (onClick) {
    const { ["data-testid"]: testId, ...buttonRest } = rest as ButtonHTMLAttributes<HTMLButtonElement> & {
      "data-testid"?: string;
    };
    return (
      <button
        {...buttonRest}
        type="button"
        title={tip}
        data-testid={testId}
        className={classes}
        onClick={onClick}
      >
        {text}
      </button>
    );
  }

  const { ["data-testid"]: testId, ...spanRest } = rest as HTMLAttributes<HTMLSpanElement> & {
    "data-testid"?: string;
  };
  return (
    <span {...spanRest} title={tip} data-testid={testId} className={classes}>
      {text}
    </span>
  );
}

export function StatusDot({ kind, tone, label, ...props }: StatusBadgeProps) {
  const resolvedTone = tone ?? mapStatusTone(kind);
  return (
    <span
      {...(props as HTMLAttributes<HTMLSpanElement>)}
      className={["ds-status-dot", statusToneClass(resolvedTone), props.className].filter(Boolean).join(" ")}
      aria-label={label ?? STATUS_KIND_LABELS[kind]}
      title={props.title ?? label ?? STATUS_KIND_LABELS[kind]}
    />
  );
}
