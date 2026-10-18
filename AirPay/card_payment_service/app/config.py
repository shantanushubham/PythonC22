"""Settings read from the environment."""

import os
from dataclasses import dataclass
from pathlib import Path

DB_ENV_VAR = "CARD_PAYMENT_DB"
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "card_payments.db"


@dataclass(frozen=True)
class Settings:
    db_path: Path


def load_settings() -> Settings:
    configured = os.environ.get(DB_ENV_VAR)
    return Settings(db_path=Path(configured) if configured else DEFAULT_DB_PATH)
