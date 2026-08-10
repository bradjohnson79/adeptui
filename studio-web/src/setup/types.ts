export type SetupComponentState =
  | "unknown"
  | "checking"
  | "ready"
  | "not_installed"
  | "update_available"
  | "installing"
  | "error"
  | "download_unavailable"
  | "source_pending";

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
  | "refresh_source"
  | "add_source_url";

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
  category?: string;
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
  source_state?: string | null;
  source_host?: string | null;
  source_type?: string | null;
  provider_id?: string | null;
  pack_version?: string | null;
  repository?: string | null;
  tag_name?: string | null;
  archive_asset_name?: string | null;
  install_disabled?: boolean | null;
  distribution_status?: string | null;
  distribution_label?: string | null;
  component_kind?: string | null;
  show_download_sizes?: boolean | null;
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
  group?: string | null;
  subgroup?: string | null;
  surfaceGroups?: string[] | null;
  parameterCount?: string | null;
  downloadSizeLabel?: string | null;
  diskUsageLabel?: string | null;
  vramRecommendationGb?: number | null;
  typicalGenerationSpeed?: string | null;
  supportedResolutions?: string[] | null;
  strengths?: string[] | null;
  weaknesses?: string[] | null;
  bestFor?: string[] | null;
  badges?: string[] | null;
  experimental?: boolean | null;
  capabilityTags?: string[] | null;
  lifecycle?: ProviderLifecycleState | null;
  lifecycle_status_label?: string | null;
  lifecycle_chain_state?: string | null;
  lifecycle_attention_state?: string | null;
  monitor_findings?: MonitorFinding[] | null;
  certified?: boolean | null;
  certified_version?: string | null;
  certified_date?: string | null;
  calibration?: CalibrationProfile | null;
  certified_recipe?: CertifiedRecipe | null;
}

export interface MonitorFinding {
  code: string;
  severity: "info" | "warning" | "error" | string;
  message: string;
  recommendedAction?: string | null;
}

export interface CalibrationProfile {
  preferredPrecision?: string | null;
  nativeResolution?: string | null;
  vramUsageGb?: number | null;
  safeBatchSize?: number | null;
  maxRecommendedResolution?: string | null;
  avgGenerationSeconds?: number | null;
  recommendedScheduler?: string | null;
  defaultCfg?: number | null;
  optimalStepCount?: number | null;
  machineProfile?: Record<string, JsonValue>;
}

export interface CertifiedRecipe {
  recipeId: string;
  componentId: string;
  title: string;
  capabilityTags?: string[];
  providerKind?: "local" | "cloud" | string;
  installStrategy?: string;
  certifiedVersion?: string | null;
  certifiedDate?: string | null;
  source?: Record<string, JsonValue>;
  requirements?: Record<string, JsonValue>;
  calibrationDefaults?: Record<string, JsonValue>;
  notes?: string[];
}

export interface ProviderLifecycleState {
  componentId: string;
  componentName: string;
  chainState?: string | null;
  attentionState?: string | null;
  statusLabel: string;
  certified?: boolean;
  certifiedRecipeId?: string | null;
  certifiedVersion?: string | null;
  certifiedDate?: string | null;
  installJobId?: string | null;
  installState?: string | null;
  verificationHealthy?: boolean | null;
  verificationSummary?: string | null;
  monitorFindings?: MonitorFinding[];
  calibration?: CalibrationProfile | null;
  recommendations?: string[];
}

export interface LifecycleInstallPlan {
  componentId: string;
  componentName: string;
  action: string;
  requiresRuntimeConfirmation: boolean;
  requiresModelDownloadConfirmation: boolean;
  destinationRoot?: string | null;
  estimatedDownloadBytes?: number | null;
  estimatedInstalledBytes?: number | null;
  currentVersion?: string | null;
  targetVersion?: string | null;
  certifiedRecipeId?: string | null;
  recommendedSource?: Record<string, JsonValue>;
  steps: string[];
  warnings: string[];
  notes: string[];
}

export interface LifecycleCloudProvider {
  providerId: string;
  displayName: string;
  statusLabel: string;
  configured: boolean;
  state?: string | null;
  operations?: string[];
  modelFamilies?: string[];
  group?: string | null;
  subgroup?: string | null;
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
  activeDownloads?: DownloadOperation[];
  installHistory?: InstallHistoryEntry[];
  diagnostics?: Record<string, JsonValue>;
  messages?: { intro?: string };
}

export interface DownloadProgress {
  bytesDownloaded?: number;
  bytesTotal?: number | null;
  percent?: number;
  speedBytesPerSecond?: number | null;
  etaSeconds?: number | null;
  currentArtifact?: string | null;
  artifactsCompleted?: number;
  artifactsTotal?: number;
}

export interface DownloadOperation {
  id: string;
  componentId: string;
  sourceId?: string | null;
  installPlanId?: string;
  providerId?: string;
  phase: string;
  priority?: number;
  queuePosition?: number | null;
  progress?: DownloadProgress;
  capabilities?: {
    canPause?: boolean;
    canResume?: boolean;
    canCancel?: boolean;
    supportsRangeRequests?: boolean;
    message?: string;
  };
  failure?: { category?: string; message?: string; recommendedAction?: string } | null;
  paths?: { stagingDirectory?: string | null; finalDestination?: string | null };
  createdAt?: string;
  updatedAt?: string;
  installId?: string;
}

export interface InstallHistoryEntry {
  id: string;
  componentId?: string;
  version?: string | null;
  providerId?: string | null;
  sourceId?: string | null;
  result?: string | null;
  installedAt?: string;
  destinationSummary?: string;
  managed?: boolean;
  kind?: string;
  fileCount?: number;
  totalSize?: number;
  verificationState?: string | null;
  rollbackAvailable?: boolean;
}

export interface InstallReceipt {
  id: string;
  componentId?: string;
  managed?: boolean;
  destinationRoot?: string;
  artifacts?: Array<{
    relativePath?: string;
    size?: number | null;
    checksum?: string | null;
    ownership?: string;
  }>;
  warnings?: string[];
  verification?: { status?: string; validatedAt?: string };
}
