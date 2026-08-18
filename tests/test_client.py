"""Error-path behaviour of the API wrapper.

These exist because of a real bug: `_call` used to catch bare TypeError to
detect an SDK without `fallbacks` support, but the SDK also raises TypeError
when it cannot resolve credentials — so a missing API key was reported as
"server-side fallbacks unavailable" and silently disabled them for the process.
"""

from __future__ import annotations

import contextlib

import anthropic
import httpx
import pytest

from halflife.config import Settings
from halflife.generation.client import CredentialsError, GenerationClient
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
