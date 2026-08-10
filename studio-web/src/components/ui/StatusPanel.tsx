import type { ReactNode } from "react";
import { Button } from "./Button";
import "./status.css";

export type StatusPanelProps = {
  title: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
  lastChecked?: string;
  onRefresh?: () => void;
  busy?: boolean;
  error?: ReactNode;
  className?: string;
  "data-testid"?: string;
};

export function StatusPanel({ title, children, actions, lastChecked, onRefresh, busy, error, className = "", "data-testid": testId }: StatusPanelProps) {
  return <section className={["ds-surface", "ds-status-panel", className].filter(Boolean).join(" ")} data-testid={testId}>
    <header><h2>{title}</h2><div className="ds-status-panel__actions">{actions}{onRefresh ? <Button variant="ghost" compact onClick={onRefresh} loading={busy}>Refresh</Button> : null}</div></header>
    {error ? <p role="alert" className="ds-status-panel__error">{error}</p> : children}
    {lastChecked ? <small>Last checked: {lastChecked}</small> : null}
  </section>;
}
