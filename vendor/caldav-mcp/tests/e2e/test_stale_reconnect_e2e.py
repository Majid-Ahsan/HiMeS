"""E2E smoke test for the stale-connection retry path.

Why this test exists
====================
Apple iCloud closes idle CalDAV HTTP keepalives after ~60-90s. When that
happens, the niquests connection pool in the `caldav` library tries to
reuse the dead socket and raises ``niquests.exceptions.ConnectionError:
keepalive timeout`` on the next CalDAV call. Before commit 86ce5e3 this
surfaced to the user as a hard "Timeout"-Error from the bot.

The fix: ``retry_on_stale_connection`` decorator on CalDAVClient's public
methods. On a stale-connection exception it reconnects once and retries.

How this test verifies the fix
==============================
It is marked ``@pytest.mark.e2e`` because it talks to the real iCloud
server (credentials from .env). It:

  1. Connects normally and calls ``list_calendars`` to warm up the pool.
  2. Monkey-patches ``caldav.principal.calendars`` to raise
     ``NiqConnError("keepalive timeout")`` exactly once. This is the
     same exception niquests throws when Apple RSTs an idle socket.
  3. Calls ``list_calendars`` again and asserts:
     - no exception is raised to the caller,
     - the patch was consumed (decorator triggered retry),
     - calendars are returned correctly.

Run with::

    CALDAV_URL=... CALDAV_USERNAME=... CALDAV_PASSWORD=... \
        pytest -m e2e tests/e2e/test_stale_reconnect_e2e.py -v

The matching unit test lives in ``tests/test_retry.py`` and covers the
decorator without hitting the network.
"""

from __future__ import annotations

import logging
import os

import pytest

from mcp_caldav.client import CalDAVClient


pytestmark = pytest.mark.e2e


@pytest.fixture
def logger_capture(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    caplog.set_level(logging.INFO, logger="mcp-caldav.stale")
    return caplog


def test_stale_connection_recovers_with_retry(
    logger_capture: pytest.LogCaptureFixture,
) -> None:
    """Inject a one-shot keepalive timeout, verify retry path runs end-to-end."""
    url = os.environ.get("CALDAV_URL")
    user = os.environ.get("CALDAV_USERNAME")
    pw = os.environ.get("CALDAV_PASSWORD")
    if not (url and user and pw):
        pytest.skip("CALDAV_URL/USERNAME/PASSWORD not set — skipping e2e test")

    # niquests is a transitive caldav dependency; the decorator matches on
    # either its ConnectionError class or well-known substrings.
    from niquests.exceptions import ConnectionError as NiqConnError

    client = CalDAVClient(url=url, username=user, password=pw)
    client.connect()

    # Warm up — populate the niquests pool with a live socket.
    warmup = client.list_calendars()
    assert warmup, "expected at least one calendar on the account"

    # Arm one-shot failure on the next principal.calendars() call. This is the
    # deepest non-network point we can inject from; the exception will bubble
    # up through list_calendars → the decorator catches it → reconnect → retry
    # (which succeeds because the flag is already cleared).
    principal_cls = type(client.principal)
    original_calendars = principal_cls.calendars
    flag = {"armed": True}

    def _one_shot(self):  # type: ignore[no-untyped-def]
        if flag["armed"]:
            flag["armed"] = False
            raise NiqConnError("keepalive timeout")
        return original_calendars(self)

    principal_cls.calendars = _one_shot
    try:
        recovered = client.list_calendars()
    finally:
        principal_cls.calendars = original_calendars

    # ── Assertions ─────────────────────────────────────────────────────────
    assert not flag["armed"], "one-shot failure should have been consumed"
    assert len(recovered) == len(warmup), (
        f"recovered list ({len(recovered)}) should match warmup ({len(warmup)})"
    )

    # Decorator emitted its telemetry.
    messages = [r.message for r in logger_capture.records if r.name == "mcp-caldav.stale"]
    assert any("stale_connection_detected" in m for m in messages), (
        f"expected stale_connection_detected in logs, got: {messages}"
    )
    assert any("retrying" in m for m in messages), (
        f"expected retrying marker in logs, got: {messages}"
    )
