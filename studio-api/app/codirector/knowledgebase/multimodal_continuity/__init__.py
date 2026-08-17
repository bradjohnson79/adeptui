"""Co-Director multimodal continuity compiler.

One structured packet → English + Chinese compiled views → provider renderers.
Does not replace I2I/reference conditioning.
"""

from .packet import compile_packet
from .provenance import stamp_continuity_packet
from .schema import COMPILER_VERSION, ContinuityCompileError, InstructionPacket
from .source_authority import assert_canon_matches_pixels, resolve_source_authority

__all__ = [
    "COMPILER_VERSION",
    "ContinuityCompileError",
    "InstructionPacket",
    "compile_packet",
    "stamp_continuity_packet",
    "assert_canon_matches_pixels",
    "resolve_source_authority",
]
