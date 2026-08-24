"""WebSocket voice tickets: no query tokens, handshake, reuse."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import config  # noqa: E402
from auth.rate_limit import reset_rate_limiter_for_tests  # noqa: E402
from auth.store import reset_store_for_tests  # noqa: E402
import main  # noqa: E402
from security import mint_voice_ticket  # noqa: E402

SECRET = "test-auth-secret-value-32chars-min"
STRONG = "Abcd1234!"


def _client(monkeypatch, tmp_path: Path) -> TestClient:
    db = str(tmp_path / "auth.sqlite")
    monkeypatch.setattr(config, "SESSION_SECRET", SECRET)
    monkeypatch.setattr(config, "AUTH_SECRET", SECRET)
    monkeypatch.setattr(config, "AUTH_DB_PATH", db)
    monkeypatch.setattr(config, "FRONTEND_ORIGINS", ["*"])
    monkeypatch.setattr(config, "ENVIRONMENT", "development")
    monkeypatch.setattr(config, "ALLOW_ANONYMOUS_WS", False)
    monkeypatch.setattr(config, "REDIS_URL", "")
    monkeypatch.setattr(config, "_REQUIRED_KEYS", {
        "SARVAM_API_KEY": "s",
        "GROQ_API_KEY": "g",
        "CARTESIA_API_KEY": "t",
    })
    reset_store_for_tests(db)
    reset_rate_limiter_for_tests()
    monkeypatch.setattr(
        main,
        "create_pipeline",
        AsyncMock(side_effect=WebSocketDisconnect()),
    )
    return TestClient(main.app)


def _signup(client: TestClient) -> str:
    response = client.post(
        "/auth/signup",
        json={"email": "ws@school.in", "password": STRONG},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_ws_rejects_query_token(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    ticket = mint_voice_ticket(user_id="00000000-0000-0000-0000-000000000001")
    with client.websocket_connect(f"/ws?token={ticket}") as ws:
        try:
            ws.receive_text()
            assert False, "query token must not authenticate"
        except WebSocketDisconnect as exc:
            assert exc.code == 4401


def test_ws_rejects_missing_and_invalid_auth(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    with client.websocket_connect("/ws") as ws:
        try:
            ws.send_text(json.dumps({"type": "auth", "token": "nope"}))
            ws.receive_text()
            assert False
        except WebSocketDisconnect as exc:
            assert exc.code == 4401


def test_ws_accepts_valid_ticket_once(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    access = _signup(client)
    minted = client.post(
        "/auth/voice-ticket",
        headers={"Authorization": f"Bearer {access}"},
    )
    token = minted.json()["token"]
    assert "token=" not in token
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "auth", "token": token}))
        message = json.loads(ws.receive_text())
        assert message["type"] == "auth_ok"

    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "auth", "token": token}))
        try:
            ws.receive_text()
            assert False, "reused ticket must fail"
        except WebSocketDisconnect as exc:
            assert exc.code == 4401
