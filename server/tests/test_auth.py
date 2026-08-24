"""User authentication, JWT, refresh rotation, and password policy."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import jwt
from fastapi.testclient import TestClient

import config  # noqa: E402
from auth import passwords  # noqa: E402
from auth.rate_limit import reset_rate_limiter_for_tests  # noqa: E402
from auth.store import hash_refresh_token, reset_store_for_tests  # noqa: E402
from auth.tokens import mint_access_token, verify_access_token  # noqa: E402
import main  # noqa: E402
from security import parse_voice_ticket  # noqa: E402


STRONG = "Abcd1234!"
SECRET = "test-auth-secret-value-32chars-min"


def _client(monkeypatch, tmp_path: Path) -> TestClient:
    db = str(tmp_path / "auth.sqlite")
    monkeypatch.setattr(config, "SESSION_SECRET", SECRET)
    monkeypatch.setattr(config, "AUTH_SECRET", SECRET)
    monkeypatch.setattr(config, "AUTH_DB_PATH", db)
    monkeypatch.setattr(config, "FRONTEND_ORIGINS", ["http://testserver"])
    monkeypatch.setattr(config, "ENVIRONMENT", "development")
    monkeypatch.setattr(config, "ALLOW_ANONYMOUS_WS", False)
    monkeypatch.setattr(config, "REDIS_URL", "")
    monkeypatch.setattr(config, "ENABLE_DEMO_LOGIN", False)
    reset_store_for_tests(db)
    reset_rate_limiter_for_tests()
    return TestClient(main.app)


def test_password_policy_rejects_weak_cases():
    assert passwords.password_policy_error("short1!") == "weak_password"
    assert passwords.password_policy_error("alllowercase1!") == "weak_password"
    assert passwords.password_policy_error("ALLUPPERCASE1!") == "weak_password"
    assert passwords.password_policy_error("NoDigits!!") == "weak_password"
    assert passwords.password_policy_error("NoSpecials1") == "weak_password"
    assert passwords.password_policy_error(STRONG) is None


def test_argon2_hash_is_not_plaintext():
    digest = passwords.hash_password(STRONG)
    assert digest != STRONG
    assert digest.startswith("$argon2id$")
    assert passwords.verify_password(digest, STRONG)
    assert not passwords.verify_password(digest, "WrongPass1!")


def test_debug_static_does_not_block_auth_post(tmp_path, monkeypatch):
    """Regression: leftover client/ UI must not steal POST /auth/* (405)."""
    client = _client(monkeypatch, tmp_path)
    created = client.post(
        "/auth/signup",
        json={"email": "static-shadow@school.in", "password": STRONG},
    )
    assert created.status_code == 200
    debug = client.get("/debug-ui/")
    assert debug.status_code == 200


def test_signup_signin_me_and_signout(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    created = client.post(
        "/auth/signup",
        json={"email": "Ada@School.IN", "password": STRONG},
    )
    assert created.status_code == 200
    body = created.json()
    assert "access_token" in body and "refresh_token" in body
    assert "password" not in body
    claims = verify_access_token(body["access_token"])
    assert claims is not None
    assert "email" not in claims
    assert claims["sub"]
    assert claims["iss"] == config.JWT_ISSUER
    assert claims["aud"] == config.JWT_AUDIENCE

    duplicate = client.post(
        "/auth/signup",
        json={"email": "ada@school.in", "password": STRONG},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "check_your_email"
    assert "access_token" not in duplicate.json()

    denied = client.post(
        "/auth/signin",
        json={"email": "ada@school.in", "password": "WrongPass1!"},
    )
    assert denied.status_code == 401
    assert denied.json()["detail"] == "invalid_credentials"

    ok = client.post(
        "/auth/signin",
        json={"email": "ada@school.in", "password": STRONG},
    )
    assert ok.status_code == 200
    access = ok.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["id"] == claims["sub"]

    spoof = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access}"},
        params={"userId": "someone-else"},
    )
    assert spoof.json()["id"] == claims["sub"]

    refresh = ok.json()["refresh_token"]
    client.post(
        "/auth/signout",
        json={"refresh_token": refresh},
        headers={"Authorization": f"Bearer {access}"},
    )
    reused = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert reused.status_code == 401


def test_signup_existing_email_does_not_reset_password(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    from auth.store import get_store

    first = client.post(
        "/auth/signup",
        json={"email": "same@school.in", "password": STRONG},
    )
    assert first.status_code == 200
    user_id = verify_access_token(first.json()["access_token"])["sub"]
    old_refresh = first.json()["refresh_token"]
    original = get_store().get_user_by_email("same@school.in")
    assert original is not None
    original_hash = original.password_hash

    again = client.post(
        "/auth/signup",
        json={"email": "same@school.in", "password": "NewPass123!"},
    )
    assert again.status_code == 409
    assert again.json()["detail"] == "check_your_email"
    assert "access_token" not in again.json()

    unchanged = get_store().get_user_by_email("same@school.in")
    assert unchanged is not None
    assert unchanged.id == user_id
    assert unchanged.password_hash == original_hash
    assert unchanged.is_active is True

    assert client.post(
        "/auth/signin",
        json={"email": "same@school.in", "password": "NewPass123!"},
    ).status_code == 401
    ok = client.post(
        "/auth/signin",
        json={"email": "same@school.in", "password": STRONG},
    )
    assert ok.status_code == 200
    rotated = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert rotated.status_code == 200


def test_signup_rejects_weak_passwords(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    for password in ("short1!", "alllowercase1!", "ALLUPPERCASE1!", "NoDigits!!", "NoSpecials1"):
        response = client.post(
            "/auth/signup",
            json={"email": "student@school.in", "password": password},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "weak_password"


def test_refresh_rotation_and_reuse_detection(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    created = client.post(
        "/auth/signup",
        json={"email": "rot@school.in", "password": STRONG},
    )
    first = created.json()["refresh_token"]
    rotated = client.post("/auth/refresh", json={"refresh_token": first})
    assert rotated.status_code == 200
    second = rotated.json()["refresh_token"]
    assert second != first
    replay = client.post("/auth/refresh", json={"refresh_token": first})
    assert replay.status_code == 401
    # Family is revoked, so the rotated token is also dead.
    also_dead = client.post("/auth/refresh", json={"refresh_token": second})
    assert also_dead.status_code == 401


def test_expired_and_invalid_jwt(monkeypatch):
    monkeypatch.setattr(config, "AUTH_SECRET", SECRET)
    monkeypatch.setattr(config, "SESSION_SECRET", SECRET)
    token = mint_access_token(user_id="user-1", now=1_000)
    assert verify_access_token(token, now=1_000) is not None
    assert verify_access_token(token, now=1_000 + config.ACCESS_TTL_SECS + 10) is None
    assert verify_access_token("not-a-jwt") is None
    assert verify_access_token(None) is None

    bad_iss = jwt.encode(
        {
            "sub": "user-1",
            "iss": "evil",
            "aud": config.JWT_AUDIENCE,
            "iat": 1_000,
            "exp": 9_999_999_999,
            "typ": "access",
            "jti": "x",
        },
        SECRET,
        algorithm="HS256",
    )
    assert verify_access_token(bad_iss, now=1_000) is None

    bad_aud = jwt.encode(
        {
            "sub": "user-1",
            "iss": config.JWT_ISSUER,
            "aud": "someone-else",
            "iat": 1_000,
            "exp": 9_999_999_999,
            "typ": "access",
            "jti": "x",
        },
        SECRET,
        algorithm="HS256",
    )
    assert verify_access_token(bad_aud, now=1_000) is None

    unsigned = jwt.encode(
        {
            "sub": "user-1",
            "iss": config.JWT_ISSUER,
            "aud": config.JWT_AUDIENCE,
            "iat": 1_000,
            "exp": 9_999_999_999,
            "typ": "access",
        },
        SECRET,
        algorithm="HS256",
    ).rsplit(".", 1)[0] + "."
    assert verify_access_token(unsigned, now=1_000) is None


def test_unauthenticated_me_and_voice_ticket(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    assert client.get("/auth/me").status_code == 401
    assert client.post("/auth/voice-ticket").status_code == 401


def test_voice_ticket_requires_user_and_is_single_use(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    created = client.post(
        "/auth/signup",
        json={"email": "voice@school.in", "password": STRONG},
    )
    access = created.json()["access_token"]
    minted = client.post(
        "/auth/voice-ticket",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert minted.status_code == 200
    token = minted.json()["token"]
    parsed = parse_voice_ticket(token)
    assert parsed is not None
    from auth.store import get_store

    assert get_store().consume_voice_jti(parsed["jti"], parsed["user_id"]) is True
    assert get_store().consume_voice_jti(parsed["jti"], parsed["user_id"]) is False


def test_refresh_token_is_stored_hashed(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    created = client.post(
        "/auth/signup",
        json={"email": "hash@school.in", "password": STRONG},
    )
    raw = created.json()["refresh_token"]
    from auth.store import get_store

    record = get_store().get_refresh_by_token(raw)
    assert record is not None
    assert record.token_hash == hash_refresh_token(raw)
    assert raw not in record.token_hash


def test_oversized_signup_rejected(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    response = client.post(
        "/auth/signup",
        json={"email": "a@b.co", "password": "A1!" + ("x" * 500)},
    )
    assert response.status_code in {400, 422}


def test_signin_rate_limit(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    client.post("/auth/signup", json={"email": "rl@school.in", "password": STRONG})
    last = None
    for _ in range(12):
        last = client.post(
            "/auth/signin",
            json={"email": "rl@school.in", "password": "WrongPass1!"},
        )
    assert last is not None
    assert last.status_code == 429


def test_legacy_credentials_are_rejected_and_not_seeded(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    from auth.store import get_store

    assert get_store().get_user_by_email("abcd@gmail.com") is None
    denied = client.post(
        "/auth/signin",
        json={"email": "abcd@gmail.com", "password": "Abcdef@123"},
    )
    assert denied.status_code == 401
    created = client.post(
        "/auth/signup",
        json={"email": "abcd@gmail.com", "password": STRONG},
    )
    assert created.status_code == 409


def test_production_ignores_demo_login_flag(tmp_path, monkeypatch):
    db = str(tmp_path / "auth.sqlite")
    monkeypatch.setattr(config, "SESSION_SECRET", SECRET)
    monkeypatch.setattr(config, "AUTH_SECRET", SECRET)
    monkeypatch.setattr(config, "AUTH_DB_PATH", db)
    monkeypatch.setattr(config, "FRONTEND_ORIGINS", ["http://testserver"])
    monkeypatch.setattr(config, "ENVIRONMENT", "production")
    monkeypatch.setattr(config, "ALLOW_ANONYMOUS_WS", False)
    monkeypatch.setattr(config, "REDIS_URL", "")
    monkeypatch.setattr(config, "ENABLE_DEMO_LOGIN", True)
    monkeypatch.setattr(config, "DEMO_LOGIN_EMAIL", "dev@localhost")
    monkeypatch.setattr(config, "DEMO_LOGIN_PASSWORD", STRONG)
    reset_store_for_tests(db)
    reset_rate_limiter_for_tests()
    from auth.store import get_store

    assert get_store().get_user_by_email("dev@localhost") is None
    assert get_store().get_user_by_email("abcd@gmail.com") is None
    client = TestClient(main.app)
    denied = client.post(
        "/auth/signin",
        json={"email": "dev@localhost", "password": STRONG},
    )
    assert denied.status_code == 401


def test_demo_login_opt_in_seeds_user_outside_production(tmp_path, monkeypatch):
    db = str(tmp_path / "auth.sqlite")
    monkeypatch.setattr(config, "SESSION_SECRET", SECRET)
    monkeypatch.setattr(config, "AUTH_SECRET", SECRET)
    monkeypatch.setattr(config, "AUTH_DB_PATH", db)
    monkeypatch.setattr(config, "FRONTEND_ORIGINS", ["http://testserver"])
    monkeypatch.setattr(config, "ENVIRONMENT", "development")
    monkeypatch.setattr(config, "ALLOW_ANONYMOUS_WS", False)
    monkeypatch.setattr(config, "REDIS_URL", "")
    monkeypatch.setattr(config, "ENABLE_DEMO_LOGIN", True)
    monkeypatch.setattr(config, "DEMO_LOGIN_EMAIL", "dev@localhost")
    monkeypatch.setattr(config, "DEMO_LOGIN_PASSWORD", STRONG)
    reset_store_for_tests(db)
    reset_rate_limiter_for_tests()
    client = TestClient(main.app)
    signed = client.post(
        "/auth/signin",
        json={"email": "dev@localhost", "password": STRONG},
    )
    assert signed.status_code == 200
    assert "access_token" in signed.json()


def test_legacy_bootstrap_row_is_locked_on_init(tmp_path, monkeypatch):
    import sqlite3
    import time as time_mod

    from auth.store import AuthStore, get_store

    db = str(tmp_path / "legacy.sqlite")
    monkeypatch.setattr(config, "ENABLE_DEMO_LOGIN", False)
    AuthStore(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO users (id, email, password_hash, is_active, created_at) "
            "VALUES (?, ?, ?, 1, ?)",
            ("legacy-id", "abcd@gmail.com", "not-a-real-hash", time_mod.time()),
        )
        conn.execute(
            "INSERT INTO refresh_sessions "
            "(id, user_id, token_hash, family_id, expires_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("sess", "legacy-id", "abc", "fam", time_mod.time() + 9_999, time_mod.time()),
        )
    reset_store_for_tests(db)
    user = get_store().get_user_by_email("abcd@gmail.com")
    assert user is not None
    assert user.is_active is False
    with sqlite3.connect(db) as conn:
        revoked = conn.execute(
            "SELECT revoked_at FROM refresh_sessions WHERE id = ?",
            ("sess",),
        ).fetchone()
    assert revoked is not None
    assert revoked[0] is not None
