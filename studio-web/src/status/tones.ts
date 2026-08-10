import type { StatusKind } from "./kinds";

export type StatusTone = "positive" | "warning" | "danger" | "neutral" | "info" | "muted";

export function mapStatusTone(kind: StatusKind): StatusTone {
  if (["Ready", "Online", "Connected", "Active", "Complete"].includes(kind)) return "positive";
  // Roadmap deferral is informational — never Failed / Missing / Blocked / Install Required.
  if (kind === "ComingInVersion12" || kind === "Deferred") return "info";
  if (["NeedsAttention", "InstallRequired", "ConfigurationRequired", "Partial", "Limited", "Pending", "Checking"].includes(kind)) return "warning";
  if (["Blocked", "Failed", "Cancelled", "Offline", "Unavailable"].includes(kind)) return "danger";
  if (["InProgress", "Queued"].includes(kind)) return "info";
  if (kind === "Unknown") return "muted";
  return "neutral";
}

export function statusToneClass(tone: StatusTone): string {
  return `ds-tone-${tone}`;
}
