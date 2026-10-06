"""Mocked tests for fal.ai queue cancel support.

No live fal.ai calls are made; all HTTP is patched in-memory.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.fal_client import FalApiError, FalAuthError, cancel_fal_request


MODEL_ID = "bytedance/seedance-2.0/text-to-video"
REQUEST_ID = "764cabcf-b745-4b3e-ae38-1200304cf45b"
API_KEY = "test-fal-key"


def _mock_client(response: MagicMock) -> MagicMock:
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.put = MagicMock(return_value=response)
    return client


def _mock_response(*, status_code: int, json_value: dict | None = None, text: str = "") -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    if json_value is not None:
        response.json = MagicMock(return_value=json_value)
    else:
        response.json = MagicMock(side_effect=ValueError("not json"))
    return response


def test_cancel_fal_request_queued_success() -> None:
    """202 Accepted returns the documented cancellation body."""
    response = _mock_response(
        status_code=202,
        json_value={"status": "CANCELLATION_REQUESTED", "request_id": REQUEST_ID},
    )
    client = _mock_client(response)

    with patch("app.fal_client.httpx.Client", return_value=client):
        result = cancel_fal_request(MODEL_ID, REQUEST_ID, API_KEY)

    assert result == {"status": "CANCELLATION_REQUESTED", "request_id": REQUEST_ID}
    client.put.assert_called_once()
    url = client.put.call_args.args[0]
    kwargs = client.put.call_args.kwargs
    assert url == f"https://queue.fal.run/{MODEL_ID}/requests/{REQUEST_ID}/cancel"
    assert kwargs["headers"]["Authorization"] == f"Key {API_KEY}"


def test_cancel_fal_request_uses_provided_cancel_url() -> None:
    """If the exact cancel_url from the submit response is stored, use it."""
    custom_url = "https://queue.fal.run/custom/requests/abc/cancel"
    response = _mock_response(status_code=200, json_value={"status": "CANCELED", "request_id": REQUEST_ID})
    client = _mock_client(response)

    with patch("app.fal_client.httpx.Client", return_value=client):
        result = cancel_fal_request(MODEL_ID, REQUEST_ID, API_KEY, cancel_url=custom_url)

    assert result["status"] == "CANCELED"
    client.put.assert_called_once()
    url = client.put.call_args.args[0]
    assert url == custom_url


def test_cancel_fal_request_missing_ids_raises() -> None:
    """Without a request id the helper cannot build a valid cancel URL."""
    with pytest.raises(FalApiError):
        cancel_fal_request(MODEL_ID, "", API_KEY)


def test_cancel_fal_request_auth_error_raises() -> None:
    """401/403 is surfaced as a credential error, not a generic failure."""
    response = _mock_response(status_code=401, text="unauthorized")
    client = _mock_client(response)

    with patch("app.fal_client.httpx.Client", return_value=client):
        with pytest.raises(FalAuthError):
            cancel_fal_request(MODEL_ID, REQUEST_ID, API_KEY)


def test_cancel_fal_request_not_found_raises() -> None:
    """404 means the request is gone or already finished — treat as a failure."""
    response = _mock_response(
        status_code=404,
        json_value={"status": "NOT_FOUND"},
    )
    client = _mock_client(response)

    with patch("app.fal_client.httpx.Client", return_value=client):
        with pytest.raises(FalApiError):
            cancel_fal_request(MODEL_ID, REQUEST_ID, API_KEY)


def test_cancel_fal_request_already_completed_raises() -> None:
    """400 ALREADY_COMPLETED means the job finished before cancel arrived."""
    response = _mock_response(
        status_code=400,
        json_value={"status": "ALREADY_COMPLETED"},
    )
    client = _mock_client(response)

    with patch("app.fal_client.httpx.Client", return_value=client):
        with pytest.raises(FalApiError):
            cancel_fal_request(MODEL_ID, REQUEST_ID, API_KEY)


def test_cancel_fal_request_malformed_json_falls_back() -> None:
    """A non-JSON success body still records the cancel as accepted."""
    response = _mock_response(status_code=202, text="accepted")
    client = _mock_client(response)

    with patch("app.fal_client.httpx.Client", return_value=client):
        result = cancel_fal_request(MODEL_ID, REQUEST_ID, API_KEY)

    assert result == {"status": "CANCELLATION_REQUESTED", "request_id": REQUEST_ID}
