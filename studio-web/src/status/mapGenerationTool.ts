import type { StatusKind } from "./kinds";

export function mapGenerationToolStatus(status: string): StatusKind {
  switch (status.trim().toUpperCase()) {
    case "COMPLETE":
    case "READY": return "Ready";
    case "PARTIAL":
    case "DEGRADED": return "Partial";
    case "BLOCKED": return "Blocked";
    case "MISSING":
    case "NOT_INSTALLED": return "InstallRequired";
    case "CONFIGURATION_REQUIRED":
    case "NOT_CONFIGURED": return "ConfigurationRequired";
    case "IN_PROGRESS":
    case "RUNNING": return "InProgress";
    case "QUEUED": return "Queued";
    case "FAILED":
    case "ERROR": return "Failed";
    case "OFFLINE": return "Offline";
    case "DEFERRED":
    case "NOT_IMPLEMENTED": return "Deferred";
    case "PENDING_CERTIFICATION":
    case "BUILT": return "Pending";
    case "CERTIFIED":
    case "PRODUCTION_READY": return "Ready";
    default: return "Unknown";
  }
}
