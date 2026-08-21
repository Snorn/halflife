"""Error-path behaviour of the API wrapper.

These exist because of a real bug: `_call` used to catch bare TypeError to
detect an SDK without `fallbacks` support, but the SDK also raises TypeError
when it cannot resolve credentials — so a missing API key was reported as
"server-side fallbacks unavailable" and silently disabled them for the process.
"""

from __future__ import annotations

import contextlib
import json
import traceback
import types

import anthropic
import httpx
import pytest

from pydantic import SecretStr

from halflife.config import Settings
from halflife.generation import client as client_module
from halflife.generation.client import CredentialsError, GenerationClient, GenerationError
from halflife.generation.schemas import GeneratedIssue

AUTH_TYPE_ERROR = TypeError(
    "Could not resolve authentication method. Expected one of api_key, auth_token, or "
    "credentials to be set."
)


def _status_error(cls, status: int, message: str):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls(message, response=httpx.Response(status, request=request), body=None)


def _bad_request(message: str) -> anthropic.BadRequestError:
    return _status_error(anthropic.BadRequestError, 400, message)


class _Endpoint:
    """Stands in for ``client.messages`` / ``client.beta.messages``.

    Generation streams, so the error under test has to surface from entering
    the stream context rather than from a plain call.
    """

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    @contextlib.contextmanager
    def stream(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        raise AssertionError("unexpected successful call in this test")
        yield  # pragma: no cover - unreachable, but makes this a generator


class _FakeSDK:
    def __init__(self, *, plain: Exception | None, beta: Exception | None) -> None:
        self.messages = _Endpoint(plain)
        self.beta = type("Beta", (), {"messages": _Endpoint(beta)})()


def _client(*, plain=None, beta=None, use_fallbacks=True) -> GenerationClient:
    client = GenerationClient(Settings(anthropic_api_key="test-key-not-used"))
    client._client = _FakeSDK(plain=plain, beta=beta)
    client._use_fallbacks = use_fallbacks
    return client


def _generate(client: GenerationClient):
    return client.generate(system="s", user="u", output_model=GeneratedIssue)


def test_missing_credentials_becomes_a_readable_error():
    client = _client(plain=AUTH_TYPE_ERROR, beta=AUTH_TYPE_ERROR)

    with pytest.raises(CredentialsError, match="ANTHROPIC_API_KEY"):
        _generate(client)


def test_missing_credentials_does_not_look_like_a_fallbacks_problem():
    """The original bug: an auth failure disabled fallbacks permanently."""
    client = _client(plain=AUTH_TYPE_ERROR, beta=AUTH_TYPE_ERROR)

    with pytest.raises(CredentialsError):
        _generate(client)

    assert client._use_fallbacks is True


def test_unrelated_type_errors_are_not_swallowed():
    client = _client(plain=TypeError("something else entirely"), beta=TypeError("something else entirely"))

    with pytest.raises(TypeError, match="something else entirely"):
        _generate(client)


def test_server_rejecting_the_fallbacks_beta_degrades_to_the_plain_endpoint():
    client = _client(
        beta=_bad_request("unsupported beta: server-side-fallback"),
        plain=AUTH_TYPE_ERROR,  # proves the plain endpoint was reached
    )

    with pytest.raises(CredentialsError):
        _generate(client)

    assert client._use_fallbacks is False
    assert client._client.messages.calls == 1


def test_other_bad_requests_are_raised_not_masked_as_a_fallbacks_problem():
    """A schema rejection must not be mistaken for the beta being unavailable."""
    client = _client(beta=_bad_request("output_config.format: schema is invalid"))

    with pytest.raises(anthropic.BadRequestError, match="schema is invalid"):
        _generate(client)

    assert client._use_fallbacks is True
    assert client._client.messages.calls == 0


def test_a_rejected_key_is_reported_without_a_traceback():
    """A 401 means the key was found and refused — a different problem from
    no key at all, and the message has to say so."""
    error = _status_error(anthropic.AuthenticationError, 401, "API key is invalid.")
    client = _client(beta=error, plain=error)

    with pytest.raises(CredentialsError, match="truncated paste"):
        _generate(client)


def test_forbidden_is_distinguished_from_invalid():
    error = _status_error(anthropic.PermissionDeniedError, 403, "Forbidden")
    client = _client(beta=error, plain=error)

    with pytest.raises(CredentialsError, match="wrong workspace"):
        _generate(client)


def test_a_rejected_key_does_not_disable_fallbacks():
    error = _status_error(anthropic.AuthenticationError, 401, "API key is invalid.")
    client = _client(beta=error, plain=error)

    with pytest.raises(CredentialsError):
        _generate(client)

    assert client._use_fallbacks is True


def test_fallback_support_is_feature_detected_from_the_sdk():
    client = GenerationClient(Settings(anthropic_api_key="test-key-not-used"))
    # The installed SDK does support it; the point is that this is decided by
    # inspecting the signature, not by catching an exception at call time.
    assert client._use_fallbacks is True


# --------------------------------------------------------- schema-fault leaks


class _Stream:
    """A stream context manager whose final message is a fixed payload."""

    def __init__(self, text: str) -> None:
        self.text = text

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        block = types.SimpleNamespace(type="text", text=self.text)
        return types.SimpleNamespace(
            stop_reason="end_turn",
            content=[block],
            usage=types.SimpleNamespace(input_tokens=1, output_tokens=1),
            model="claude-opus-5",
        )


class _Returning:
    def __init__(self, text: str) -> None:
        self.text = text

    def stream(self, **kwargs):
        return _Stream(self.text)


def _client_returning(text: str) -> GenerationClient:
    client = GenerationClient(Settings(anthropic_api_key="test-key-not-used"))
    client._client = types.SimpleNamespace(
        messages=_Returning(text),
        beta=types.SimpleNamespace(messages=_Returning(text)),
    )
    return client


SENSITIVE = "The session table is consulted before the balancing logic runs"


@pytest.mark.parametrize(
    "payload",
    [
        json.dumps(
            {
                "title": "T",
                "body_markdown": [SENSITIVE],  # wrong type: pydantic echoes the value
                "covered_points_added": [],
                "open_threads": [],
                "next_suggested": "n",
                "plan_index": 0,
            }
        ),
        json.dumps({"title": "T", "next_suggested": SENSITIVE}),  # missing fields
        '{"title": "T", "body_markdown": "' + SENSITIVE + '"',  # truncated JSON
    ],
    ids=["wrong-type", "missing-fields", "bad-json"],
)
def test_a_malformed_response_never_quotes_itself(payload):
    """CLAUDE.md forbids model output in error payloads, and pydantic puts the
    offending value in its message as input_value=... . The chained cause is
    dropped too, because a chained exception prints that message in the
    traceback even when ours does not."""
    with pytest.raises(GenerationError) as caught:
        _generate(_client_returning(payload))

    rendered = "".join(
        traceback.format_exception(type(caught.value), caught.value, caught.value.__traceback__)
    )
    assert SENSITIVE[:25] not in str(caught.value)
    assert SENSITIVE[:25] not in rendered
    assert "input_value" not in rendered
    assert caught.value.__cause__ is None


def test_the_fault_still_says_which_field_and_why():
    """Stripping the value must not strip the diagnosis with it."""
    payload = json.dumps(
        {
            "title": "T",
            "body_markdown": 12345,
            "covered_points_added": [],
            "open_threads": [],
            "next_suggested": "n",
            "plan_index": 0,
        }
    )
    with pytest.raises(GenerationError, match=r"body_markdown: string_type"):
        _generate(_client_returning(payload))


def test_the_sdk_is_handed_the_key_itself_not_the_wrapper(monkeypatch):
    """The unwrap is easy to forget, and forgetting it authenticates with the
    string "**********" — which fails at the API rather than at import."""
    captured = {}

    class _Recording:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.messages = _Endpoint(None)
            self.beta = type("Beta", (), {"messages": _Endpoint(None)})()

    monkeypatch.setattr(client_module.anthropic, "Anthropic", _Recording)

    GenerationClient(Settings(anthropic_api_key="sk-ant-api03-not-a-real-key"))

    assert captured["api_key"] == "sk-ant-api03-not-a-real-key"
    assert not isinstance(captured["api_key"], SecretStr)
