from datetime import datetime, timedelta, timezone

import jwt

from utils import security


def test_password_hash_round_trip():
    hashed = security.hash_password("secret-pass")
    assert hashed != "secret-pass"
    assert security.verify_password("secret-pass", hashed)
    assert not security.verify_password("wrong", hashed)


def test_access_and_refresh_tokens_are_not_interchangeable():
    access = security.create_access_token("1")
    refresh = security.create_refresh_token("1")

    assert security.decode_access_token(access)["sub"] == "1"
    assert security.decode_refresh_token(refresh)["sub"] == "1"
    assert security.decode_access_token(refresh) is None
    assert security.decode_refresh_token(access) is None


def test_expired_token_is_rejected():
    expired = jwt.encode(
        {
            "sub": "1",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        security.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )
    assert security.decode_access_token(expired) is None


def test_token_signed_with_another_key_is_rejected():
    forged = jwt.encode(
        {
            "sub": "1",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        "some-other-secret-key-of-enough-length",
        algorithm=security.ALGORITHM,
    )
    assert security.decode_access_token(forged) is None


def test_garbage_token_is_rejected():
    assert security.decode_access_token("not-a-jwt") is None
