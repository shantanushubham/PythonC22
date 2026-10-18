"""Write the OpenAPI spec to openapi.json.

Run from the card_payment_service directory:

    uv run python scripts/export_openapi.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

SPEC_PATH = ROOT / "openapi.json"


def render_spec() -> str:
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    SPEC_PATH.write_text(render_spec())
    print(f"Wrote {SPEC_PATH}")


if __name__ == "__main__":
    main()
