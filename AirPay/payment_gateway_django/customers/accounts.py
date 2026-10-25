"""Encrypt bank account numbers and hash them for uniqueness.

The full account number is needed to send a payout, so it is stored with Fernet
(AES-128-CBC + HMAC). The hash lets us reject a duplicate without decrypting
every row. The last four digits are kept in the clear so the customer can
recognise the account.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

IFSC_PATTERN = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
ACCOUNT_NUMBER_PATTERN = re.compile(r"^\d{9,18}$")


def _material() -> bytes:
    configured = getattr(settings, "BANK_ACCOUNT_KEY", "") or ""
    if configured:
        return hashlib.sha256(configured.encode("utf-8")).digest()
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"), b"airpay-bank-account-v1", hashlib.sha256
    ).digest()


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_material()))


def normalize_ifsc(value: str) -> str:
    return (value or "").strip().upper()


def normalize_account_number(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def encrypt_account_number(account_number: str) -> str:
    return _fernet().encrypt(account_number.encode("ascii")).decode("ascii")


def decrypt_account_number(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("ascii")
    except InvalidToken as error:
        raise ValueError("Stored account number could not be decrypted.") from error


def account_fingerprint(ifsc: str, account_number: str) -> str:
    payload = f"{ifsc}:{account_number}".encode("ascii")
    return hmac.new(_material(), payload, hashlib.sha256).hexdigest()
