import json

import httpx
import pytest
from django.test import override_settings

from cviky import llm
from cviky.llm import ExerciseDraft, structure_exercise

SETTINGS = override_settings(OPENROUTER_API_KEY="test-key", OPENROUTER_MODEL="test/model")


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error", request=httpx.Request("POST", llm.OPENROUTER_URL), response=self
            )


def _llm_response(draft: dict) -> FakeResponse:
    return FakeResponse({"choices": [{"message": {"content": json.dumps(draft)}}]})


FULL = {
    "title": "Uvolnění krku",
    "area": "krk",
    "position": "sed",
    "tags": ["krční páteř", "šíje"],
    "steps": "Pomalu otáčej hlavu.",
    "cautions": "Nepřekračuj bolest.",
    "reps": "10× na každou stranu",
}


def _patch_post(monkeypatch, response):
    calls = {}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["kwargs"] = kwargs
        return response

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    return calls


@SETTINGS
def test_valid_response_maps_fields(monkeypatch):
    _patch_post(monkeypatch, _llm_response(FULL))
    draft = structure_exercise("popis cviku")
    assert draft.area == "krk"
    assert draft.position == "sed"
    assert draft.tags == ["krční páteř", "šíje"]
    assert draft.title == "Uvolnění krku"
    assert draft.steps == "Pomalu otáčej hlavu."
    assert draft.cautions == "Nepřekračuj bolest."
    assert draft.reps == "10× na každou stranu"


@SETTINGS
def test_unknown_area_becomes_empty(monkeypatch):
    payload = dict(FULL, area="hlava")
    _patch_post(monkeypatch, _llm_response(payload))
    draft = structure_exercise("popis cviku")
    assert draft.area == ""
    assert draft.position == "sed"
    assert draft.title == "Uvolnění krku"
    assert draft.tags == ["krční páteř", "šíje"]


@SETTINGS
def test_tags_are_normalized(monkeypatch):
    payload = dict(FULL, tags=["  Krční Páteř ", "", "šíje", "šíje", "  "])
    _patch_post(monkeypatch, _llm_response(payload))
    draft = structure_exercise("popis cviku")
    assert draft.tags == ["krční páteř", "šíje"]


@SETTINGS
def test_tags_string_is_split_on_commas(monkeypatch):
    payload = dict(FULL, tags="krční páteř, šíje")
    _patch_post(monkeypatch, _llm_response(payload))
    assert structure_exercise("popis cviku").tags == ["krční páteř", "šíje"]


@SETTINGS
def test_request_uses_short_timeout(monkeypatch):
    calls = _patch_post(monkeypatch, _llm_response(FULL))
    structure_exercise("popis cviku")
    timeout = calls["kwargs"]["timeout"]
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 5.0
    assert timeout.read == 20.0


@SETTINGS
def test_non_json_returns_empty_draft(monkeypatch):
    _patch_post(monkeypatch, FakeResponse({"choices": [{"message": {"content": "not json"}}]}))
    assert structure_exercise("popis cviku") == ExerciseDraft()


@SETTINGS
def test_timeout_returns_empty_draft(monkeypatch):
    def fake_post(url, **kwargs):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    assert structure_exercise("popis cviku") == ExerciseDraft()


@SETTINGS
def test_http_500_returns_empty_draft(monkeypatch):
    _patch_post(monkeypatch, FakeResponse({}, status_code=500))
    assert structure_exercise("popis cviku") == ExerciseDraft()


@SETTINGS
def test_request_sends_zdr_and_deny(monkeypatch):
    calls = _patch_post(monkeypatch, _llm_response(FULL))
    structure_exercise("popis cviku")
    body = calls["kwargs"]["json"]
    assert body["provider"] == {"zdr": True, "data_collection": "deny"}
    assert body["response_format"]["type"] == "json_schema"
    assert calls["url"] == llm.OPENROUTER_URL


@pytest.mark.parametrize("key,value", [("OPENROUTER_API_KEY", ""), ("OPENROUTER_MODEL", "")])
def test_missing_config_returns_empty_draft(monkeypatch, key, value):
    def fail_post(*args, **kwargs):
        raise AssertionError("httpx.post must not be called without config")

    monkeypatch.setattr(llm.httpx, "post", fail_post)
    overrides = {"OPENROUTER_API_KEY": "test-key", "OPENROUTER_MODEL": "test/model", key: value}
    with override_settings(**overrides):
        assert structure_exercise("popis cviku") == ExerciseDraft()
