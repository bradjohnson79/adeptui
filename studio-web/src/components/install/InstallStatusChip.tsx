import { useSyncExternalStore } from "react";
import {
  getInstallBadgeForComponent,
  getInstallJobForComponent,
  subscribeInstallJobs,
  getInstallJobsSnapshot,
} from "../../state/installJobsStore";
import "./install-progress.css";

function toneFromBadge(badge: string): string {
  const value = badge.toLowerCase();
  if (value.includes("ready")) return "ready";
  if (value.includes("repair") || value.includes("failed") || value.includes("blocked")) return "repair";
  if (value.includes("download") || value.includes("install") || value.includes("stall") || value.includes("waiting")) {
    return "downloading";
  }
  return "default";
}

export function InstallStatusChip({
  componentId,
  href,
}: {
  componentId: string;
  href?: string;
}) {
  useSyncExternalStore(subscribeInstallJobs, getInstallJobsSnapshot, getInstallJobsSnapshot);
  const badge = getInstallBadgeForComponent(componentId);
  const job = getInstallJobForComponent(componentId);
  if (!job && badge === "Not installed") return null;
  const tone = toneFromBadge(badge);
  const className = `install-status-chip install-status-chip--${tone}`;
  if (href) {
    return (
      <a className={className} href={href} data-testid={`install-status-chip-${componentId}`}>
        {badge}
      </a>
    );
  }
  return (
    <span className={className} data-testid={`install-status-chip-${componentId}`}>
      {badge}
    </span>
  );
}
