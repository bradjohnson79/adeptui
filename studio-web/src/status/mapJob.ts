import type { StatusKind } from "./kinds";

export function mapJobStatus(status: string): StatusKind {
  switch (status.trim().toLowerCase()) {
    case "queued": return "Queued";
    case "running":
    case "in_progress":
    case "processing": return "InProgress";
    case "done":
    case "complete":
    case "completed": return "Complete";
    case "failed":
    case "error": return "Failed";
    case "cancelled":
    case "canceled": return "Cancelled";
    case "pending": return "Pending";
    default: return "Unknown";
  }
}
