"""Final render checkpoints stay on the existing job and never move progress backward."""

from app.magi.final_render import note_stage, upscale_requested


class _Job:
    def __init__(self):
        self.stage = ""
        self.message = ""
        self.progress = 0.05
        self.history_json = None


class _Db:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def test_upscale_off_without_an_engine_does_not_request_upscale():
    assert upscale_requested({"enabled": False}) is False
    assert upscale_requested({"enabled": False, "engine": "ffmpeg-scale"}) is True
    assert upscale_requested({"enabled": True, "engine": "ffmpeg-scale", "target": "1440p"}) is True
    assert upscale_requested(None) is False


def test_note_stage_appends_real_checkpoints_and_keeps_progress_monotonic():
    job = _Job()
    db = _Db()
    note_stage(db, job, "Preparing scene", "Validating current MAGI settings…", 0.08)
    note_stage(db, job, "Rendering final frames", "Rendering final frames…", 0.18)
    note_stage(db, job, "Rendering final frames", "Rendering final frames…", 0.1)
    assert job.progress == 0.18
    assert job.stage == "Rendering final frames"
    assert db.commits == 3
    import json

    history = json.loads(job.history_json)
    assert [item["message"] for item in history["stages"]] == [
        "Validating current MAGI settings…",
        "Rendering final frames…",
    ]
