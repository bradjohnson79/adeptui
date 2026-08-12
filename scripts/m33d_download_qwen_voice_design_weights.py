"""Explicit Hugging Face snapshot download for Qwen VoiceDesign (user-initiated)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG_ID = "m2101-voice-design-021"
SOURCE = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"


def main() -> int:
    sandbox = ROOT / "data" / "m210b-sandbox" / "providers" / REG_ID
    models = sandbox / "models"
    models.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import snapshot_download
    except Exception as exc:
        print(f"huggingface_hub required: {exc}", file=sys.stderr)
        return 2
    print(f"Downloading {SOURCE} into {models} (this is multi-GB; user-initiated).")
    snapshot_download(repo_id=SOURCE, local_dir=str(models))
    manifest_path = sandbox / "install-manifest.json"
    data = {}
    if manifest_path.is_file():
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data.update(
        {
            "installed": True,
            "registryId": REG_ID,
            "sourceKey": SOURCE,
            "weightsDownloadedAt": datetime.now(timezone.utc).isoformat(),
        }
    )
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("Weights downloaded; mark venv ready separately if not already.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
