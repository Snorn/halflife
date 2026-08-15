"""Error-path behaviour of the API wrapper.

These exist because of a real bug: `_call` used to catch bare TypeError to
detect an SDK without `fallbacks` support, but the SDK also raises TypeError
when it cannot resolve credentials — so a missing API key was reported as
"server-side fallbacks unavailable" and silently disabled them for the process.
"""

from __future__ import annotations

import anthropic
import httpx
import pytest

from halflife.config import Settings
from halflife.generation.client import GenerationClient, MissingCredentials
from halflife.generation.schemas import GeneratedIssue

AUTH_TYPE_ERROR = TypeError(
    "Could not resolve authentication method. Expected one of api_key, auth_token, or "
    "credentials to be set."
)


def _bad_request(message: str) -> anthropic.BadRequestError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(400, request=request)
    return anthropic.BadRequestError(message, response=response, body=None)


class _Endpoint:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        raise AssertionError("unexpected successful call in this test")


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

    with pytest.raises(MissingCredentials, match="ANTHROPIC_API_KEY"):
        _generate(client)


def test_missing_credentials_does_not_look_like_a_fallbacks_problem():
    """The original bug: an auth failure disabled fallbacks permanently."""
    client = _client(plain=AUTH_TYPE_ERROR, beta=AUTH_TYPE_ERROR)

    with pytest.raises(MissingCredentials):
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

    with pytest.raises(MissingCredentials):
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


def test_fallback_support_is_feature_detected_from_the_sdk():
    client = GenerationClient(Settings(anthropic_api_key="test-key-not-used"))
    # The installed SDK does support it; the point is that this is decided by
    # inspecting the signature, not by catching an exception at call time.
    assert client._use_fallbacks is True
