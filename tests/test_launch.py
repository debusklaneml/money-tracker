"""Unit tests for the launcher's host-resolution logic.

These do NOT start uvicorn; they only exercise the pure env-reading and
URL-substitution helpers in ``backend.launch``.
"""

import backend.launch as launch


def test_host_defaults_to_loopback(monkeypatch):
    monkeypatch.delenv("BUD_HOST", raising=False)
    assert launch._host() == "127.0.0.1"


def test_host_blank_falls_back_to_loopback(monkeypatch):
    monkeypatch.setenv("BUD_HOST", "")
    assert launch._host() == "127.0.0.1"


def test_host_override(monkeypatch):
    monkeypatch.setenv("BUD_HOST", "0.0.0.0")
    assert launch._host() == "0.0.0.0"


def test_host_override_specific_ip(monkeypatch):
    monkeypatch.setenv("BUD_HOST", "192.168.1.10")
    assert launch._host() == "192.168.1.10"


def test_browsable_host_keeps_loopback():
    assert launch._browsable_host("127.0.0.1") == "127.0.0.1"


def test_browsable_host_substitutes_bind_all():
    # 0.0.0.0 / :: are bind addresses, not browsable destinations.
    assert launch._browsable_host("0.0.0.0") == "127.0.0.1"
    assert launch._browsable_host("::") == "127.0.0.1"


def test_browsable_host_keeps_real_host():
    assert launch._browsable_host("192.168.1.10") == "192.168.1.10"
