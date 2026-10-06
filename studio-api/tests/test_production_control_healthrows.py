
"""Production Control must not report Co-Director LLM Available at modelCount=0."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_codirector_healthrow_requires_installed_model() -> None:
    from app.production_control.status import aggregate_status

    cfg = {"endpoint": "http://127.0.0.1:11434", "selectedModel": "qwen3.6:35b-a3b"}

    class _Resp:
        def read(self) -> bytes:
            return b'{"models": []}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("app.production_control.status.load_config", return_value=cfg), patch(
        "urllib.request.urlopen", return_value=_Resp()
    ):
        payload = aggregate_status()
    row = next(item for item in payload["healthRows"] if item["id"] == "codirector")
    assert row["status"] != "Available"
    assert payload["codirector"]["modelCount"] == 0
    assert payload["codirector"]["modelAvailable"] is False
