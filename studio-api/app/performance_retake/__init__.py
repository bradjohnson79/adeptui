"""Performance Retake — whole-window performance replacement.

A Lip Sync request is a performance replacement: the original video+audio
inside the retake window is removed and a new performance is rendered for
that window by MiniMax H3 Reference-to-Video (source video + character
sheets + per-line voice renders). No crop composite, no audio layering.

Governing doc: docs/release-gate/performance-retake/PERFORMANCE_RETAKE_ARCHITECTURE.md
"""
