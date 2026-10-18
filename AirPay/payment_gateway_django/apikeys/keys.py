"""Making, parsing and hashing API keys. No database in here.

A key looks like this:

    apk_3f9a1c07b2de_9c1e...(64 hex characters)...

    apk_            marks it as an AirPay API key, so leaked keys are easy to spot
    3f9a1c07b2de    the prefix: a public id, used to find the key and to tell keys apart
    9c1e...         the secret: 256 random bits, from the operating system's secure
                    random number generator

Only a hash of the whole key is stored. The full key is shown once, when it is created.

Why a keyed hash and not encryption: the server never needs to read a key back, only to
check one. A one way hash cannot be reversed even by someone who has the database *and*
the code. Why HMAC-SHA256 and not bcrypt: bcrypt is slow on purpose, to make guessing weak
human passwords expensive. These keys are 256 random bits and cannot be guessed, so a
fast hash is safe, and it keeps every API call quick.
"""

import hmac
import re
import secrets
from dataclasses import dataclass

from django.conf import settings
from django.utils.crypto import salted_hmac

KEY_PREFIX = "apk_"
PREFIX_BYTES = 6  # 12 hex characters
SECRET_BYTES = 32  # 256 bits

_KEY_PATTERN = re.compile(r"^apk_(?P<prefix>[0-9a-f]{12})_(?P<secret>[0-9a-f]{64})$", re.ASCII)

# Used to run the same comparison when no key matches, so a request for an unknown key
# takes about as long as a request with a known prefix.
_NO_MATCH_DIGEST = "0" * 64


@dataclass(frozen=True)
class GeneratedKey:
    raw: str  # shown to the customer once, never stored
    prefix: str  # stored, public
    digest: str  # stored


def generate_key() -> GeneratedKey:
    prefix = secrets.token_hex(PREFIX_BYTES)
    secret = secrets.token_hex(SECRET_BYTES)
    raw = f"{KEY_PREFIX}{prefix}_{secret}"
    return GeneratedKey(raw=raw, prefix=prefix, digest=hash_key(raw))


def hash_key(raw: str) -> str:
    """HMAC-SHA256 of the key, as 64 hex characters.

    The hash is keyed with API_KEYS["PEPPER"], which lives in the environment and not in
    the database. A copy of the database alone cannot be used to check guesses.
    """
    return salted_hmac(
        "airpay.apikeys.v1",
        raw,
        secret=settings.API_KEYS["PEPPER"],
        algorithm="sha256",
    ).hexdigest()


def parse_prefix(raw: str) -> str | None:
    """The prefix of a well formed key, or None if the text is not shaped like a key."""
    match = _KEY_PATTERN.fullmatch(raw) if isinstance(raw, str) else None
    return match.group("prefix") if match else None


def digests_match(stored: str | None, presented: str) -> bool:
    """Compare two hashes in constant time. `stored` is None when no key was found."""
    return hmac.compare_digest(stored or _NO_MATCH_DIGEST, presented) and stored is not None
