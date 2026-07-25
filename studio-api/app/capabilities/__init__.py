"""Capability registry: the machine-readable answer to "can this be used right now?".

`registry.py` holds what the code can do (static, from code inspection). `probes.py` asks the
environment what is actually present. `service.py` combines them into one honest status per
capability, and `api.py` publishes it. Consumers must never re-derive readiness themselves.
"""

from .models import (  # noqa: F401
    CapabilityBlockerOut,
    CapabilityDefinition,
    CapabilityOut,
    CapabilitySnapshotOut,
    CapabilityStatus,
)
from .registry import CAPABILITIES, SUBSYSTEMS, get_definition, list_definitions  # noqa: F401

__all__ = [
    "CAPABILITIES",
    "SUBSYSTEMS",
    "CapabilityBlockerOut",
    "CapabilityDefinition",
    "CapabilityOut",
    "CapabilitySnapshotOut",
    "CapabilityStatus",
    "get_definition",
    "list_definitions",
]
