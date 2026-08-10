import type { ReactNode } from "react";
import { Button } from "../ui";

type AdvancedDrawerProps = {
  open: boolean;
  title?: string;
  summary: string;
  children: ReactNode;
  onToggle: () => void;
};

export function AdvancedDrawer({
  open,
  title = "Advanced options",
  summary,
  children,
  onToggle,
}: AdvancedDrawerProps) {
  return (
    <section className={`audio-advanced${open ? " is-open" : ""}`} data-testid="audio-advanced">
      <div className="audio-advanced__header">
        <div>
          <p className="audio-advanced__eyebrow">{title}</p>
          <p className="audio-advanced__summary">{summary}</p>
        </div>
        <Button variant="ghost" onClick={onToggle} aria-expanded={open}>
          {open ? "Hide details" : "Show details"}
        </Button>
      </div>
      {open ? <div className="audio-advanced__body">{children}</div> : null}
    </section>
  );
}
