"""Shared test setup."""

import pytest

from app.container import get_payment_repository
from app.main import app
from app.repositories.sqlite_payment_repository import SqlitePaymentRepository


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path):
    """Give every test its own empty database by replacing the repository dependency."""
    repository = SqlitePaymentRepository(tmp_path / "payments.db")
    app.dependency_overrides[get_payment_repository] = lambda: repository
    yield repository
    app.dependency_overrides.clear()
