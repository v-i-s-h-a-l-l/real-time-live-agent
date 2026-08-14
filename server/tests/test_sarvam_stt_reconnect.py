"""Sarvam STT must reconnect instead of staying dead after a socket drop."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.sarvam_stt import disable_websockets_protocol_ping  # noqa: E402


def test_disable_protocol_ping_cancels_keepalive_task():
    cancelled = {"n": 0}

    class FakeTask:
        def done(self):
            return False

        def cancel(self):
            cancelled["n"] += 1

    ws = SimpleNamespace(ping_interval=20, keepalive_ping_task=FakeTask())
    socket = SimpleNamespace(_websocket=ws)
    disable_websockets_protocol_ping(socket)
    assert ws.ping_interval is None
    assert cancelled["n"] == 1


def test_disable_protocol_ping_ignores_missing_socket():
    disable_websockets_protocol_ping(None)
    disable_websockets_protocol_ping(SimpleNamespace())


def test_pipeline_uses_reconnecting_sarvam_stt():
    source = (ROOT / "pipeline.py").read_text(encoding="utf-8")
    assert "ReconnectingSarvamSTTService" in source
    assert "from pipecat.services.sarvam.stt import SarvamSTTService" not in source
