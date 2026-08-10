export type StatusKind =
  | "Ready" | "Online" | "Connected" | "Active" | "Complete" | "InProgress"
  | "Queued" | "Pending" | "Checking" | "NeedsAttention" | "InstallRequired"
  | "ConfigurationRequired" | "Partial" | "Limited" | "Offline" | "Unavailable"
  | "Blocked" | "Failed" | "Cancelled" | "Deferred" | "ComingInVersion12" | "Unknown";

export const STATUS_KIND_LABELS: Record<StatusKind, string> = {
  Ready: "Ready", Online: "Online", Connected: "Connected", Active: "Active",
  Complete: "Complete", InProgress: "In progress", Queued: "Queued", Pending: "Pending",
  Checking: "Checking", NeedsAttention: "Needs attention", InstallRequired: "Install required",
  ConfigurationRequired: "Configuration required", Partial: "Partial", Limited: "Limited",
  Offline: "Offline", Unavailable: "Unavailable", Blocked: "Blocked", Failed: "Failed",
  Cancelled: "Cancelled", Deferred: "Deferred", ComingInVersion12: "Coming in Version 1.2",
  Unknown: "Unknown",
};
