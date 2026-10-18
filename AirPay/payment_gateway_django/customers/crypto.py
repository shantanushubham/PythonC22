"""API key material: random generation and a keyed hash for storage.

A key looks like ``apk_<lookup>_<secret>``. The lookup is stored in the clear so a
request can find the right row. The secret is 256 bits from the OS CSPRNG
(``secrets.token_bytes``) and is never written down.

What is stored is ``HMAC-SHA256(pepper, full_key)``. That is a keyed hash, not
reversible encryption: a copy of the database cannot be turned back into working
keys. HMAC is used instead of bcrypt because the secret is already high-entropy,
so stretching would only slow every payment request.

The pepper is ``API_KEY_PEPPER`` when that is set, otherwise a key derived from
``SECRET_KEY``. Changing the pepper invalidates every API key.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass

from django.conf import settings

SCHEME = "apk"
LOOKUP_BYTES = 8  # 16 hex characters
SECRET_BYTES = 32  # 256 bits of key material

_KEY_PATTERN = re.compile(rf"^{SCHEME}_([0-9a-f]{{{LOOKUP_BYTES * 2}}})_[A-Za-z0-9_-]+$")


@dataclass(frozen=True, slots=True)
class KeyMaterial:
    raw: str
    prefix: str
    last_four: str
    secret_hash: str


def pepper() -> bytes:
    """32-byte HMAC key. A dedicated pepper is preferred so rotating JWT secrets
    does not revoke every API key."""
    configured = getattr(settings, "API_KEY_PEPPER", "") or ""
    if configured:
        return hashlib.sha256(configured.encode("utf-8")).digest()
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), b"airpay-api-key-v1", hashlib.sha256).digest()


def generate() -> KeyMaterial:
    """Build a new key. Each call asks the OS for fresh random bytes."""
    lookup = secrets.token_hex(LOOKUP_BYTES)
    secret = secrets.token_urlsafe(SECRET_BYTES)
    raw = f"{SCHEME}_{lookup}_{secret}"
    return KeyMaterial(
        raw=raw,
        prefix=f"{SCHEME}_{lookup}",
        last_four=secret[-4:],
        secret_hash=digest(raw),
    )


def digest(raw: str) -> str:
    return hmac.new(pepper(), raw.encode("ascii"), hashlib.sha256).hexdigest()


def prefix_of(raw: str) -> str | None:
    """The stored lookup prefix, or None when the string is not an AirPay API key."""
    match = _KEY_PATTERN.fullmatch(raw.strip())
    return f"{SCHEME}_{match.group(1)}" if match else None


def verify(raw: str, stored_hash: str | None) -> bool:
    """True only when `raw` is the secret that produced `stored_hash`.

    The HMAC always runs, even for a missing row, so a guess that matches no
    prefix does not return faster than a guess that matches a prefix.
    """
    candidate = digest(raw)
    expected = stored_hash if stored_hash is not None else "0" * 64
    matched = hmac.compare_digest(candidate, expected)
    return bool(matched and stored_hash is not None)
