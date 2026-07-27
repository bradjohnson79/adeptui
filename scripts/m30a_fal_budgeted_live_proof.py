"""M3.0a C2: one budgeted live fal.ai render, then stop.

Submits exactly one short Seedance text-to-video job through the same code path the
API uses (`build_fal_arguments` -> `run_fal_model` -> `extract_video_url`), downloads
the artifact, and writes a secret-free JSON summary.

Safety rules enforced here:
  * the key is read from `.env` only and is never printed, logged, or written out;
    every message that could carry it is scrubbed first
  * one submit per invocation - after the queue accepts the job there is no resubmit
    on any failure path
  * refuses to run again if a completed summary already exists (pass --force to override)

Usage:  python scripts/m30a_fal_budgeted_live_proof.py
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "studio-api"))

from app.fal_catalog import build_fal_arguments  # noqa: E402
from app.fal_client import (  # noqa: E402
    FalApiError,
    download_url,
    extract_video_url,
    fetch_fal_account_usage,
    run_fal_model,
    validate_fal_key,
)

BUDGET_CAP_USD = 5.00
# Published Seedance 2.0 pricing is well under this for 4s @ 480p without audio; the
# ceiling is deliberately pessimistic so the guard trips before the cap, not after.
ESTIMATED_MAX_COST_USD = 1.00

KEY_NAMES = ("FAL_API_KEY", "FAL_KEY", "ADEPT_M30A_FAL_KEY")
OUT_DIR = REPO_ROOT / "artifacts" / "m30a-fal"
VIDEO_PATH = OUT_DIR / "seedance_t2v_4s_480p.mp4"
SUMMARY_PATH = OUT_DIR / "live_proof_summary.json"

PROMPT = (
    "Cinematic slow dolly-in across an empty film studio at dawn, dust motes drifting "
    "through a single shaft of window light, shallow depth of field, warm amber grade."
)

_SECRETS: list[str] = []


def scrub(text: Any) -> str:
    out = str(text)
    for secret in _SECRETS:
        if secret:
            out = out.replace(secret, "***REDACTED***")
    return out


def say(msg: str) -> None:
    print(f"[m30a-fal] {scrub(msg)}", flush=True)


def load_env_file(path: Path) -> dict[str, str]:
    """Minimal dotenv parse - no dependency, no export of values."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, raw = line.partition("=")
        raw = raw.strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
            raw = raw[1:-1]
        values[name.strip()] = raw
    return values


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_summary(payload: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    say(f"summary -> {SUMMARY_PATH.relative_to(REPO_ROOT)}")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="re-run even if a summary exists")
    args = parser.parse_args()

    started = datetime.now(timezone.utc)
    summary: dict[str, Any] = {
        "outcome": "aborted",
        "engine": "fal_seedance",
        "model_id": None,
        "request_id": None,
        "duration_sec": 4,
        "resolution": "480p",
        "aspect_ratio": None,
        "seed": 42,
        "generate_audio": False,
        "artifact_path": None,
        "file_size_bytes": None,
        "sha256": None,
        "budget_cap_usd": BUDGET_CAP_USD,
        "estimated_max_cost_usd": ESTIMATED_MAX_COST_USD,
        "submitted": False,
        "timestamp_utc": started.isoformat().replace("+00:00", "Z"),
        "notes": [],
    }

    if SUMMARY_PATH.exists() and not args.force:
        prior = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        if prior.get("submitted"):
            say("a job was already submitted by a previous run; refusing to spend again (--force to override)")
            return 3

    env = load_env_file(REPO_ROOT / ".env")
    key = ""
    key_source = None
    for name in KEY_NAMES:
        candidate = (env.get(name) or "").strip()
        if candidate:
            key, key_source = candidate, name
            break
    if not key:
        summary["notes"].append(f"no fal key in .env (looked for {', '.join(KEY_NAMES)})")
        write_summary(summary)
        say("ABORT: no fal key found in .env")
        return 2
    _SECRETS.append(key)
    summary["key_source"] = key_source
    summary["key_length"] = len(key)
    say(f"key loaded from .env as {key_source} (length {len(key)}); value never printed")

    # Step 1 - free credential probe. A failure here must not lead to a paid submit.
    validation = await validate_fal_key(key)
    summary["validation"] = {
        "valid": validation.get("valid"),
        "status": validation.get("status"),
        "httpStatus": validation.get("httpStatus"),
        "probeEndpoint": validation.get("probeEndpoint"),
    }
    say(f"validate_fal_key -> status={validation.get('status')} http={validation.get('httpStatus')}")
    if validation.get("valid") is not True:
        summary["notes"].append(f"validation not verified: {scrub(validation.get('message'))}")
        write_summary(summary)
        say("ABORT: key not verified; no job submitted, nothing spent")
        return 2

    # Step 2 - best-effort budget check. Usage/billing needs an ADMIN key, so a refusal
    # here is informational, not a blocker; a known balance that cannot cover the job is.
    try:
        usage = await fetch_fal_account_usage(key, days=1)
    except Exception as exc:  # noqa: BLE001 - usage is advisory only
        usage = {"ok": False, "errors": [scrub(exc)]}
    balance = usage.get("balance")
    summary["balance_before"] = balance
    summary["usage_ok"] = bool(usage.get("ok"))
    summary["usage_needs_admin_key"] = bool(usage.get("needs_admin_key"))
    if balance is None:
        summary["notes"].append("account balance unavailable (usage/billing needs an ADMIN-scoped key)")
        say("balance unavailable - proceeding under the fixed one-job cap")
    else:
        say(f"balance before: {balance} {usage.get('currency') or 'USD'}")
        if float(balance) <= 0:
            summary["notes"].append("balance is zero or negative; refusing to submit")
            write_summary(summary)
            say("ABORT: no credit balance")
            return 2
    if ESTIMATED_MAX_COST_USD > BUDGET_CAP_USD:
        summary["notes"].append("estimated cost exceeds session budget cap")
        write_summary(summary)
        say("ABORT: estimated cost over budget")
        return 2

    # Step 3 - build args exactly as the API would (no start image -> T2V fallback).
    model_id, arguments = build_fal_arguments(
        engine="fal_seedance",
        prompt=PROMPT,
        negative="",
        image_url=None,
        end_image_url=None,
        duration_sec=4,
        width=854,
        height=480,
        seed=42,
        generate_audio=False,
    )
    summary["model_id"] = model_id
    summary["aspect_ratio"] = arguments.get("aspect_ratio")
    summary["arguments"] = arguments
    say(f"model_id={model_id} args={json.dumps(arguments)}")

    request_id_box: dict[str, str] = {}

    async def on_request_id(rid: str) -> None:
        request_id_box["id"] = rid
        summary["request_id"] = rid
        say(f"request_id={rid}")

    async def on_progress(pct: float, msg: str) -> None:
        say(f"progress {pct:.0%} - {msg}")

    # Step 4 - ONE submit. Everything after this point is read-only against fal.
    say("submitting one job now (single attempt, no resubmit on failure)")
    summary["submitted"] = True
    submit_started = datetime.now(timezone.utc)
    try:
        result = await run_fal_model(
            model_id,
            arguments,
            key,
            on_progress=on_progress,
            on_request_id=on_request_id,
            timeout_sec=600.0,
        )
    except FalApiError as exc:
        summary["outcome"] = "failed"
        summary["notes"].append(f"fal error: {scrub(exc)}")
        write_summary(summary)
        say(f"FAILED: {exc}")
        return 1

    summary["wall_clock_sec"] = round((datetime.now(timezone.utc) - submit_started).total_seconds(), 1)
    summary["result_keys"] = sorted(result.keys())

    try:
        video_url = extract_video_url(result)
    except FalApiError as exc:
        summary["outcome"] = "failed"
        summary["notes"].append(f"no video url in result: {scrub(exc)}")
        write_summary(summary)
        say(f"FAILED: {exc}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    await download_url(video_url, VIDEO_PATH)
    size = VIDEO_PATH.stat().st_size
    summary["artifact_path"] = str(VIDEO_PATH.relative_to(REPO_ROOT)).replace("\\", "/")
    summary["file_size_bytes"] = size
    summary["sha256"] = sha256_of(VIDEO_PATH)
    summary["outcome"] = "verified" if size > 0 else "failed"
    if size <= 0:
        summary["notes"].append("downloaded file is empty")

    try:
        usage_after = await fetch_fal_account_usage(key, days=1)
        summary["balance_after"] = usage_after.get("balance")
        if balance is not None and usage_after.get("balance") is not None:
            summary["observed_cost_usd"] = round(float(balance) - float(usage_after["balance"]), 4)
    except Exception as exc:  # noqa: BLE001
        summary["notes"].append(f"post-run usage unavailable: {scrub(exc)}")

    summary["completed_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    write_summary(summary)
    say(f"OUTCOME={summary['outcome']} bytes={size} sha256={summary['sha256']}")
    say("done - hard stop, no further jobs")
    return 0 if summary["outcome"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
