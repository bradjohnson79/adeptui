"""Universal Adept Launcher.

One native entry point that runs before the Electron application on every
supported desktop platform. It is the single update authority: it reads the
installed version, verifies the signed release catalog, applies an update from
outside the replaceable payload, then starts the application. Electron performs
no update handoff.
"""

from __future__ import annotations

__version__ = "1.1.6"
