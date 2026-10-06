from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.character_identity.voice_runtime import generate_voice_design_sample


def test_generate_voice_design_sample_uses_warm_serve_without_token_cap(tmp_path):
    dest = tmp_path / "design.wav"
    dest.write_bytes(b"RIFF" + b"\x00" * 1200)
    proc = SimpleNamespace(
        stdin=MagicMock(),
        stdout=MagicMock(),
        poll=MagicMock(return_value=None),
    )
    proc.stdout.readline.return_value = (
        '{"type":"done","id":"job1xxxxxx","first_audio_ms":1200,"complete_ms":1800,"device":"cuda:0"}\n'
    )

    with (
        patch(
            "app.character_identity.voice_runtime._project_audio_dir",
            return_value=tmp_path,
        ),
        patch(
            "app.character_identity.voice_runtime._design_serve",
            return_value={"proc": proc, "ready": {"device": "cuda:0"}},
        ),
        patch(
            "app.character_identity.voice_runtime.validate_generated_wav",
            return_value=None,
        ),
        patch("app.character_identity.voice_runtime.uuid.uuid4") as uuid4,
    ):
        uuid4.return_value = SimpleNamespace(hex="job1xxxxxx")
        produced = generate_voice_design_sample(
            project_id="p1",
            text="Hey there.",
            instruct="Playful teenage elf",
            seed=1,
            preview=True,
        )

    written = proc.stdin.write.call_args[0][0]
    assert '"preview": false' in written
    assert "max_new_tokens" not in written
    assert produced["warm_worker"] is True
    assert produced["engine"] == "qwen3-tts"
    assert produced["complete_ms"] == 1800
