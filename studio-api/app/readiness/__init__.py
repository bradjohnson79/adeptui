"""Studio readiness contract: installed, running, owned, executable.

v1.1 production-readiness classes live in ``v11_policy`` — that is the single
authority for Production Assurance and the Capability Registry.
"""

from .contract import (
    READY_REQUIRES_FILESYSTEM_PATH,
    apply_files_ready_gate,
    discover_model_roots,
    is_filesystem_install_path,
    readiness_axes,
)
from .v11_policy import (
    POLICY_VERSION,
    SCORE_SEMANTICS,
    ReadinessClass,
    classify_capability,
    classify_status_check,
    videochat3_v11_decision,
)

__all__ = [
    "POLICY_VERSION",
    "READY_REQUIRES_FILESYSTEM_PATH",
    "ReadinessClass",
    "SCORE_SEMANTICS",
    "apply_files_ready_gate",
    "classify_capability",
    "classify_status_check",
    "discover_model_roots",
    "is_filesystem_install_path",
    "readiness_axes",
    "videochat3_v11_decision",
]
