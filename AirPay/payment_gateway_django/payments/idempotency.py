import hashlib
import json
import re

from rest_framework.exceptions import ValidationError

_KEY = re.compile(r"^[A-Za-z0-9._:-]{1,255}$")


def read_key(request) -> str:
    key = (request.headers.get("Idempotency-Key") or "").strip()
    if key == "":
        return ""
    if not _KEY.fullmatch(key):
        raise ValidationError({"non_field_errors": ["Idempotency-Key is invalid"]})
    return key


def fingerprint(*parts) -> str:
    payload = json.dumps(list(parts), separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
