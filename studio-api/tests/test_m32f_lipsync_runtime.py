from pathlib import Path

from app.workflows.lipsync_runtime import (
    extract_output_path_from_history,
    lipsync_no_output_error,
    summarize_comfy_failure,
)


def test_summarize_comfy_failure_detects_decord():
    message = summarize_comfy_failure(
        {
            "status": {
                "status_str": "error",
                "messages": [["ModuleNotFoundError: No module named 'decord'"]],
            }
        }
    )
    assert message == (
        "LatentSync dependency missing: install decord in the ComfyUI Python environment"
    )


def test_summarize_comfy_failure_detects_no_face():
    message = summarize_comfy_failure(
        {"status": {"messages": [["Unable to detect face in source video"]]}}
    )
    assert message == (
        "Lip sync needs a face-forward speaking clip; the source video has no detectable face"
    )


def test_lipsync_no_output_error_is_concise():
    error = lipsync_no_output_error(
        {"status": {"messages": [["No output was written", "traceback: " + ("x" * 2000)]]}}
    )
    assert len(str(error)) <= 400
    assert "traceback" not in str(error).lower() or len(str(error)) < 100


def test_extract_output_path_from_history_finds_string_path(tmp_path):
    output = tmp_path / "lipsync.mp4"
    output.write_bytes(b"video")
    history = {"outputs": {"2": {"string": str(output)}}}

    assert extract_output_path_from_history(history) == output
