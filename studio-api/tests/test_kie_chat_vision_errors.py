"""Kie chat envelope parsing stays honest for Kie image/chat adapters.

Co-Director Vision no longer uses Kie. These tests keep the adapter from
collapsing {code, msg} again if other Kie chat callers remain.
"""

from __future__ import annotations

from app.hosted_providers.adapters.kie_adapter import kie_chat_failure_from_payload


def test_kie_envelope_401_is_the_error():
    err = kie_chat_failure_from_payload(
        {"code": 401, "msg": "The API key is not authorized to use this model.", "data": None},
        200,
    )
    assert err == "The API key is not authorized to use this model."


def test_kie_http_200_empty_choices_is_not_ok():
    err = kie_chat_failure_from_payload({"choices": []}, 200)
    assert err == "Kie returned no vision text."


def test_kie_openai_content_is_success():
    err = kie_chat_failure_from_payload(
        {"choices": [{"message": {"content": '{"hair":"black"}'}}]},
        200,
    )
    assert err is None
