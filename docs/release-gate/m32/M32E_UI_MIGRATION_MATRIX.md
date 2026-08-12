# M3.2e UI Migration Matrix

| Surface | Status | Primitives | Notes |
|---|---|---|---|
| SystemStatusStrip | Migrated | StatusBadge, useStudioHealth | testids kept |
| CapabilityReadinessPanel | Migrated | SectionHeader, ReadinessMeter, StatusBadge | no derived readiness |
| CapabilityStatusBadge | Migrated | StatusBadge | Ready / NeedsAttention / Unknown |
| GenerationToolsHub | Migrated | StatusBadge, mapGenerationToolStatus | BLOCKED preserved |
| JobPanel | Migrated | EmptyState, StatusBadge, Button | traceback disclosure |
| Home library / sections | Partial | SectionHeader, EmptyState | carousel preserved |
| Source Manager | Migrated | StatusBadge, ds-surface | Offline ≠ Blocked |
| Co-Director summaries | Deferred light | — | cinematic shell quarantined |
| Editor timeline / canvas | Deferred Tier 3 | — | documented only |
| SetupWizard progress | Deferred Tier 3 | — | setup-specific |
