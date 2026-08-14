"""Account passwords: Argon2id hashing and policy checks.

Hashing is intentionally expensive and must only run on signup/signin —
never on the voice audio path.
"""

from __future__ import annotations

import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

PASSWORD_MIN_LEN = 8
PASSWORD_MAX_LEN = 128

_UPPER = re.compile(r"[A-Z]")
_LOWER = re.compile(r"[a-z]")
_DIGIT = re.compile(r"[0-9]")
_SPECIAL = re.compile(r"[^A-Za-z0-9]")

# 64 MiB, 3 iterations, single thread — suitable for a 2 GB Render instance.
_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=1,
    hash_len=32,
    salt_len=16,
)

# Precomputed dummy so unknown-email sign-in still runs Argon2 (timing).
_DUMMY_HASH = _HASHER.hash("lumina-dummy-password-not-used")


def password_policy_error(password: str) -> str | None:
    if not isinstance(password, str):
        return "weak_password"
    if len(password) < PASSWORD_MIN_LEN or len(password) > PASSWORD_MAX_LEN:
        return "weak_password"
    if not _UPPER.search(password):
        return "weak_password"
    if not _LOWER.search(password):
        return "weak_password"
    if not _DIGIT.search(password):
        return "weak_password"
    if not _SPECIAL.search(password):
        return "weak_password"
    return None


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _HASHER.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False


def verify_dummy(password: str) -> None:
    """Burn the same CPU as a real verify so missing accounts don't time-oracle."""
    try:
        _HASHER.verify(_DUMMY_HASH, password)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return
