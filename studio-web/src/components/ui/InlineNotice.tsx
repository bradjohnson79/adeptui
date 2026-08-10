import type { ReactNode } from "react";
import "./empty-state.css";

export type InlineNoticeVariant = "loading" | "error" | "install-required" | "blocked" | "info";
export function InlineNotice({ variant, children, className = "" }: { variant: InlineNoticeVariant; children: ReactNode; className?: string }) {
  return <div className={["ds-inline-notice", `ds-inline-notice--${variant}`, className].filter(Boolean).join(" ")} role={variant === "error" || variant === "blocked" ? "alert" : "status"}>{children}</div>;
}
