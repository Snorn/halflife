"""Settings loading.

The BOM case is here because it cost a failed eval run: Windows PowerShell's
`Out-File -Encoding utf8` writes a byte-order mark, and with plain utf-8 the
first key in .env parses as "﻿HALFLIFE_..." and never matches. The failure
is silent — settings load fine, the value is simply absent — and surfaces much
later as "no credentials found" while the file plainly contains the key.
"""

from __future__ import annotations

import pytest

from halflife.config import Settings


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path / ".env"


def _write(path, text: str, *, bom: bool) -> None:
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def test_reads_a_plain_utf8_env_file(env_file):
    _write(env_file, "HALFLIFE_ANTHROPIC_API_KEY=plain-value\n", bom=False)
    assert Settings().anthropic_api_key == "plain-value"


def test_reads_an_env_file_written_with_a_bom(env_file):
    _write(env_file, "HALFLIFE_ANTHROPIC_API_KEY=bom-value\n", bom=True)
    assert Settings().anthropic_api_key == "bom-value"


def test_bom_does_not_leak_into_the_value(env_file):
    _write(env_file, "HALFLIFE_MODEL_ID=claude-opus-5\n", bom=True)
    assert Settings().model_id == "claude-opus-5"


def test_environment_beats_the_env_file(env_file, monkeypatch):
    _write(env_file, "HALFLIFE_EFFORT=low\n", bom=True)
    monkeypatch.setenv("HALFLIFE_EFFORT", "max")
    assert Settings().effort == "max"


def test_defaults_when_nothing_is_set(env_file):
    assert Settings().anthropic_api_key is None
    assert Settings().model_id == "claude-opus-5"
    # medium, not high: measured better on the depth eval and ~60% cheaper.
    # See the note in config.py before changing this.
    assert Settings().effort == "medium"
