"""Production Bible: versioned project knowledge grounding for Co-Director (M2.1).

The model never mutates the Bible directly. Reads flow through `ProjectContextService`
(bounded excerpt injected into chat context); writes flow through `proposals.ProposalService`
(persisted proposal → explicit approval → execution → new immutable version + receipt).
"""

from __future__ import annotations
