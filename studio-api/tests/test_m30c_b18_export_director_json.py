"""M3.0c B18 regression: export scene payload retains director_json."""

from __future__ import annotations

import inspect


def test_export_source_includes_director_json():
    from app import queue_worker

    source = inspect.getsource(queue_worker.JobQueue._export)
    assert "director_json" in source
