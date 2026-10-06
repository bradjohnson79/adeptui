"""Spatial Reconstruction Compiler — intermediate Atlas reconstruction.

Perception determines structure. The structural guide encodes topology.
The image model only renders. Map assignment happens only after the
three-question visual gate. This package is a sibling of SpatialDraft:
it is not a production field on SpatialMapDocument and does not mutate
frozen PerceptionPacket.
"""

from .contracts import (
    EvidenceKind,
    FeatureRecord,
    GeometrySanityResult,
    ReconstructionCamera,
    ReconstructionLayout,
    ScaleRecord,
    SpatialReconstructionPacket,
    UnknownRegion,
)
from .compiler import prepare_reconstruction_for_atlas
from .persist import load_reconstruction_packet, save_reconstruction_packet
from .sanity import validate_geometry_sanity

__all__ = [
    "EvidenceKind",
    "FeatureRecord",
    "GeometrySanityResult",
    "ReconstructionCamera",
    "ReconstructionLayout",
    "ScaleRecord",
    "SpatialReconstructionPacket",
    "UnknownRegion",
    "load_reconstruction_packet",
    "prepare_reconstruction_for_atlas",
    "save_reconstruction_packet",
    "validate_geometry_sanity",
]
