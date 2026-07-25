"""Print the live capability snapshot for this machine.

Used to fill in the readiness report with real values instead of remembered ones. Run from
`studio-api/`:

    .venv/Scripts/python.exe scripts/dump_capability_snapshot.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.capabilities import service  # noqa: E402


async def main() -> None:
    snapshot = await service.get_capabilities(force=True)
    print(f"generatedAt: {snapshot.generatedAt}")
    print(f"total: {len(snapshot.capabilities)}  callable: {len(snapshot.callable)}")
    print()
    print("counts:")
    for status, count in sorted(snapshot.counts.items()):
        print(f"  {status}: {count}")
    print()
    print("callable:")
    for capability_id in snapshot.callable:
        print(f"  {capability_id}")
    print()
    print("blockers:")
    for blocker in snapshot.blockers:
        print(f"  {blocker.capabilityId} [{blocker.status.value}] {blocker.reasonCode}")
        print(f"      {blocker.message}")
        print(f"      action={blocker.recommendedAction} components={blocker.componentIds}")
    print()
    print(f"probeWarnings: {snapshot.probeWarnings}")


if __name__ == "__main__":
    asyncio.run(main())
