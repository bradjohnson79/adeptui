export type SetupComponentState =
  | "unknown"
  | "checking"
  | "ready"
  | "not_installed"
  | "update_available"
  | "installing"
  | "error"
  | "download_unavailable";

export type SetupOperationPhase =
  | "installing"
  | "updating"
  | "repairing"
  | "configuring"
  | "verifying"
  | "validating"
  | "downloading"
  | "verifying_download"
  | "extracting"
  | "verifying_install"
  | "completed"
  | "failed";

export type SetupOperationState =
  | "queued"
  | "running"
  | "awaiting_checkpoint"
  | "finalizing"
  | "completed"
  | "failed"
  | "cancelled"
  | "interrupted";

export type DiagnosticRecommendation =
  | "none"
  | "install"
  | "repair"
  | "reinstall"
  | "update"
  | "correct_path"
  | "grant_permission"
  | "configure"
  | "manual_help"
  | "link_existing"
  | "choose_install_location"
  | "refresh_source";

export type SetupPrimaryActionKind =
  | "install"
  | "diagnostics"
  | "recommended_action"
  | "update"
  | "refresh_source"
  | "link_existing"
  | "choose_install_location"
  | "add_source_url"
  | "manual_help";

export type DownloadSourceStatus =
  | "Ready"
  | "Installed but not authenticated"
  | "Not installed"
  | "Misconfigured"
  | "Unavailable"
  | "Verification failed";

export interface DownloadSourceCliStatus {
  provider: "github" | "huggingface" | string;
  status: DownloadSourceStatus | string;
  cli_detected: boolean;
  executable_path?: string | null;
  executable_name?: string | null;
  version?: string | null;
  authenticated: boolean;
  account_name?: string | null;
  token_available: boolean;
  last_verified_at?: string | null;
  message?: string;
  diagnostics?: Record<string, JsonValue>;
}

export interface DownloadSourcesResponse {
  github: DownloadSourceCliStatus;
  huggingface: DownloadSourceCliStatus;
  package_managers?: string[];
  overrides?: Record<string, JsonValue>;
  messages?: {
    discovery_failed?: string;
    add_source_help?: string;
  };
}

export interface SourceVerificationResult {
  ok: boolean;
  compatibility?: string;
  source?: Record<string, JsonValue> | null;
  provider?: string;
  repository?: string | null;
  revision?: string | null;
  selected_file?: string | null;
  size?: number | null;
  checksum?: string | null;
  authentication_status?: string;
  authentication_required?: boolean;
  installation_method?: string;
  files?: Array<{ name?: string; path?: string; size?: number | null; kind?: string }>;
  warnings?: string[];
  blocking_errors?: Array<{ code?: string; message: string }>;
  verification_fingerprint?: string;
  message?: string;
  component_id?: string | null;
}

export type SetupCheckpointKind =
  | "path"
  | "model_path"
  | "manual_installer"
  | "manual_help"
  | "credentials"
  | "elevation"
  | "license"
  | "disk_space";

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export interface SetupPrimaryAction {
  kind?: SetupPrimaryActionKind;
  action?: SetupPrimaryActionKind;
  label: string;
  disabled?: boolean;
}

export interface ComponentDiagnosticResult {
  component_id?: string;
  healthy: boolean;
  issue_code?: string | null;
  summary: string;
  technical_details?: string[];
  recommendation: DiagnosticRecommendation;
  recommended_action_label?: string | null;
  requires_user_interaction: boolean;
  checked_at: string;
}

export interface SetupComponentStatus {
  id: string;
  name: string;
  description: string;
  purpose?: string;
  required: boolean;
  status: SetupComponentState;
  operation_phase?: SetupOperationPhase | null;
  operation_id?: string | null;
  installed_version?: string | null;
  available_version?: string | null;
  installation_path?: string | null;
  last_verified_at?: string | null;
  progress?: number | null;
  stage?: string | null;
  estimated_remaining_seconds?: number | null;
  issue_code?: string | null;
  issue_summary?: string | null;
  diagnostic?: ComponentDiagnosticResult | null;
  primary_action?: SetupPrimaryAction | null;
  download_bytes?: number | null;
  installed_bytes?: number | null;
  estimated_installed_bytes?: number | null;
  expected_download_bytes?: number | null;
  expected_installed_bytes?: number | null;
  download_size_bytes?: number | null;
  installed_size_bytes?: number | null;
  download_size_mb?: number | null;
  installed_size_mb?: number | null;
  install_kind?: "detect_only" | "download" | "path_link" | "manual" | "credentials" | "asset_pack" | string;
  installer?: "detect_only" | "download" | "path_link" | "manual" | "credentials" | "asset_pack" | string;
  path_selector?: "directory" | "file" | null;
  verifier?: string | null;
  source_valid?: boolean | null;
  source_available?: boolean | null;
  source_host?: string | null;
  source_type?: string | null;
  provider_id?: string | null;
  pack_version?: string | null;
  repository?: string | null;
  tag_name?: string | null;
  archive_asset_name?: string | null;
  install_disabled?: boolean | null;
  secondary_action?: SetupPrimaryAction | null;
  tertiary_action?: SetupPrimaryAction | null;
  pack_actions?: SetupPrimaryAction[] | null;
  custom_source_active?: boolean | null;
  required_files?: string[] | null;
  modes?: string[];
  min_vram_gb?: number | null;
  recommended_vram_gb?: number | null;
  source_repo?: string | null;
  license?: string | null;
  dependencies?: string[];
  logs?: string[];
  executable_path?: string | null;
  environment?: Record<string, JsonValue>;
}

export interface SetupSummaryCounts {
  ready: number;
  not_installed: number;
  needs_attention: number;
  update_available?: number;
}

export type SetupOverallStatus =
  | "ready"
  | "preparing"
  | "additional_setup_required"
  | "needs_attention";

export interface SetupStatusResponse {
  overall_status?: SetupOverallStatus;
  overall_label?: string;
  counts?: SetupSummaryCounts;
  summary?: SetupSummaryCounts;
  components: SetupComponentStatus[];
  active_operation?: SetupOperation | null;
  environment?: Record<string, JsonValue>;
  checked_at?: string;
}

export interface SetupPlannedAction {
  component_id: string;
  component_name?: string;
  action: string;
  description?: string;
  download_bytes?: number;
  estimated_seconds?: number | null;
}

export interface SetupCheckpoint {
  checkpoint_id?: string;
  id?: string;
  type?: SetupCheckpointKind;
  kind?: SetupCheckpointKind;
  title?: string;
  message?: string;
  summary?: string;
  component_id?: string | null;
  required_fields?: string[];
  field_label?: string | null;
  suggested_path?: string | null;
  path_selector?: "directory" | "file" | null;
  help_url?: string | null;
  license_url?: string | null;
  license_name?: string | null;
  license?: string | null;
  requires_license_acceptance?: boolean;
  may_require_elevation?: boolean;
  action_label?: string | null;
  action?: string | null;
  workflow?: "download_install" | "link_existing" | string | null;
}

export interface StudioPreparationPlan {
  required_actions: SetupPlannedAction[];
  skipped_optional_component_ids: string[];
  required_disk_bytes: number;
  available_disk_bytes?: number | null;
  estimated_seconds?: number | null;
  user_checkpoints: SetupCheckpoint[];
  can_run_unattended: boolean;
}

export interface SetupOperation {
  operation_id: string;
  status: SetupOperationState;
  phase?: SetupOperationPhase | null;
  component_ids?: string[];
  component_id?: string | null;
  progress?: number | null;
  stage?: string | null;
  message?: string | null;
  estimated_remaining_seconds?: number | null;
  elapsed_seconds?: number | null;
  checkpoint?: SetupCheckpoint | null;
  logs?: Array<string | { at: string; message: string }>;
  error?: string | null;
}

export interface SetupOperationStart {
  operation_id: string;
  operation?: SetupOperation;
}

export interface SetupCheckpointAnswer {
  checkpoint_id?: string;
  accepted?: boolean;
  license_accepted?: boolean;
  path?: string;
  completed?: boolean;
  cancelled?: boolean;
}

export interface SetupLegacyActionResult {
  status: string;
  message?: string;
  component?: Record<string, JsonValue>;
}

export interface SetupUpdateDismissal {
  component_id: string;
  dismissed: boolean;
}

export interface SetupLegacyCatalogComponent {
  id: string;
  name: string;
  description: string;
  purpose: string;
  required: boolean;
  download_size_mb: number;
  installed_size_mb: number;
  min_vram_gb: number;
  recommended_vram_gb: number;
  modes: string[];
  source_repo: string;
  license: string;
  install_kind: string;
}

export interface SetupLegacyDetection {
  catalog: SetupLegacyCatalogComponent[];
  gpu?: Record<string, JsonValue>;
  ram_gb?: number | null;
  disk_free_gb?: number | null;
  python?: Record<string, JsonValue>;
  ffmpeg?: Record<string, JsonValue>;
  comfyui?: Record<string, JsonValue>;
  ollama?: Record<string, JsonValue>;
  fal_key?: Record<string, JsonValue>;
  paths?: Record<string, JsonValue>;
  installed?: Record<string, JsonValue>;
}

export interface SetupLegacyState {
  components?: Record<string, JsonValue>;
  model_locations?: Record<string, string>;
}

/** Phase 1 Source Manager */
export interface SourceManagerProvider {
  id: string;
  displayName: string;
  status: string;
  available: boolean;
  executablePath?: string | null;
  version?: string | null;
  authenticated?: boolean;
  accountName?: string | null;
  tokenAvailable?: boolean;
  capabilities?: string[];
  priority: number;
  lastVerifiedAt?: string | null;
  message?: string;
  diagnostics?: Record<string, JsonValue>;
}

export interface SourceRecord {
  id: string;
  provider: string;
  sourceType: string;
  sourceUrl: string;
  displayName?: string;
  owner?: string | null;
  repository?: string | null;
  revision?: string | null;
  assetPath?: string | null;
  authenticationRequired?: boolean;
  verificationStatus?: string;
  verifiedAt?: string | null;
  verificationFingerprint?: string | null;
  userDefined?: boolean;
  componentsUsing?: string[];
  artifactCount?: number;
  metadata?: Record<string, JsonValue>;
}

export interface SourceManagerOverview {
  schemaVersion: number;
  providers: SourceManagerProvider[];
  sources: SourceRecord[];
  assignments?: Record<string, JsonValue>;
  activeDownloads?: JsonValue[];
  installHistory?: JsonValue[];
  diagnostics?: Record<string, JsonValue>;
  messages?: { intro?: string };
}
