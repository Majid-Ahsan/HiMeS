"""Test retry_on_stale_connection decorator behaviour.

Separated file so it can be added to the caldav-mcp repo without
touching the existing test file.
"""
from unittest.mock import MagicMock, patch

import pytest

from mcp_caldav.client import (
    CalDAVClient,
    _is_stale_connection_error,
    retry_on_stale_connection,
)


class _FakeNiquestsConnError(Exception):
    """Simulates niquests.exceptions.ConnectionError message."""


# ── _is_stale_connection_error ──────────────────────────────────────────────


def test_stale_error_by_message():
    assert _is_stale_connection_error(RuntimeError("keepalive timeout"))
    assert _is_stale_connection_error(RuntimeError("Connection reset by peer"))
    assert _is_stale_connection_error(RuntimeError("Remote end closed connection"))


def test_stale_error_via_cause_chain():
    """list_calendars wraps the original as RuntimeError(...) from e."""
    original = Exception("keepalive timeout")
    wrapped = RuntimeError("Failed to list calendars: keepalive timeout")
    wrapped.__cause__ = original
    assert _is_stale_connection_error(wrapped)


def test_non_stale_errors_pass_through():
    assert not _is_stale_connection_error(ValueError("bad input"))
    assert not _is_stale_connection_error(PermissionError("401 Unauthorized"))
    assert not _is_stale_connection_error(FileNotFoundError("404 Not Found"))
    assert not _is_stale_connection_error(RuntimeError("calendar does not exist"))


# ── retry_on_stale_connection decorator ─────────────────────────────────────


class _DummyClient:
    """Minimal CalDAVClient-shaped object for decorator testing."""

    def __init__(self):
        self.connect_calls = 0
        self.method_calls = 0
        self.next_errors: list[Exception] = []

    def connect(self):
        self.connect_calls += 1

    @retry_on_stale_connection
    def do_thing(self, arg):
        self.method_calls += 1
        if self.next_errors:
            raise self.next_errors.pop(0)
        return f"ok:{arg}"


def test_retry_success_path():
    """No error → no retry, no reconnect."""
    c = _DummyClient()
    assert c.do_thing("foo") == "ok:foo"
    assert c.method_calls == 1
    assert c.connect_calls == 0


def test_retry_reconnects_and_succeeds():
    """First call raises stale, second call (after reconnect) succeeds."""
    c = _DummyClient()
    c.next_errors = [RuntimeError("keepalive timeout")]
    assert c.do_thing("bar") == "ok:bar"
    assert c.method_calls == 2  # original + retry
    assert c.connect_calls == 1


def test_retry_only_once():
    """If second call also fails, error is raised (no third attempt)."""
    c = _DummyClient()
    c.next_errors = [
        RuntimeError("keepalive timeout"),
        RuntimeError("keepalive timeout"),
    ]
    with pytest.raises(RuntimeError, match="keepalive timeout"):
        c.do_thing("baz")
    assert c.method_calls == 2
    assert c.connect_calls == 1


def test_non_stale_errors_are_not_retried():
    """Auth errors, ValueError, etc. pass through untouched."""
    c = _DummyClient()
    c.next_errors = [PermissionError("401 Unauthorized")]
    with pytest.raises(PermissionError):
        c.do_thing("qux")
    assert c.method_calls == 1  # no retry
    assert c.connect_calls == 0


def test_reconnect_failure_surfaces_original_or_connect_error():
    """If reconnect itself fails, we raise (don't swallow)."""
    c = _DummyClient()
    c.next_errors = [RuntimeError("keepalive timeout")]

    def _bad_connect():
        raise OSError("network down")

    c.connect = _bad_connect  # type: ignore[assignment]
    with pytest.raises(OSError, match="network down"):
        c.do_thing("bang")


def test_connect_not_decorated():
    """connect() must remain the retry primitive — no loop risk."""
    # The real CalDAVClient.connect has no @retry_on_stale_connection
    # because the decorator calls self.connect() on failure; decorating
    # connect itself would loop. Verify it's still a plain method.
    assert not hasattr(CalDAVClient.connect, "__wrapped__") or \
        CalDAVClient.connect.__wrapped__ is CalDAVClient.connect
