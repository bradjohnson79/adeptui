import type { CapabilityStatus } from "../capabilities";
import type { StatusKind } from "./kinds";

export function mapCapabilityStatus(status: CapabilityStatus): StatusKind {
  switch (status) {
    case "blocked": return "Blocked";
    case "not_configured": return "ConfigurationRequired";
    case "degraded":
    case "partially_wired": return "Partial";
    case "locally_verified":
    case "production_ready": return "Ready";
    case "mock_verified": return "Limited";
    case "not_implemented":
    case "backend_only":
    case "ui_only": return "Unavailable";
    default: return "Unknown";
  }
}
