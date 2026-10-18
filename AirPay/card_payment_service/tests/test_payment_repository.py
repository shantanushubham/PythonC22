"""Repository contract.

The same tests run against every implementation. If a new repository passes them, the
services can use it without changes (Liskov Substitution).
"""

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.repositories.payment_repository import (
    DuplicateIdempotencyKeyError,
    DuplicatePaymentError,
)
from app.repositories.sqlite_payment_repository import SqlitePaymentRepository
from app.container import build_payment_service
from app.exceptions import IdempotencyConflictError
from tests.fakes import InMemoryPaymentRepository, make_payment, make_record, make_request


@pytest.fixture(params=["sqlite", "in_memory"])
def repository(request, tmp_path):
    if request.param == "sqlite":
        return SqlitePaymentRepository(tmp_path / "contract.db")
    return InMemoryPaymentRepository()


def test_payment_round_trips_exactly(repository):
    repository.save(make_payment("txn_1", key="k1"))

    loaded = repository.get("txn_1")

    assert loaded is not None
    assert loaded.record == make_record("txn_1")
    assert loaded.fingerprint == "fp-1"
    assert loaded.idempotency_key == "k1"


def test_declined_payment_round_trips(repository):
    repository.save(make_payment("txn_2", status="FAILED"))

    loaded = repository.get("txn_2")

    assert loaded.record.status == "FAILED"
    assert loaded.record.failure_reason == "Insufficient funds"
    assert loaded.record.authorization_code is None


def test_lookup_by_idempotency_key(repository):
    repository.save(make_payment("txn_3", key="k3"))

    assert repository.get_by_key("k3").record.transaction_id == "txn_3"


def test_unknown_ids_return_none(repository):
    assert repository.get("txn_missing") is None
    assert repository.get_by_key("missing") is None


def test_duplicate_idempotency_key_is_rejected_and_not_stored(repository):
    repository.save(make_payment("txn_a", key="same"))

    with pytest.raises(DuplicateIdempotencyKeyError):
        repository.save(make_payment("txn_b", key="same"))

    assert repository.get("txn_b") is None
    assert repository.get_by_key("same").record.transaction_id == "txn_a"


def test_duplicate_transaction_id_is_rejected(repository):
    repository.save(make_payment("txn_dup"))

    with pytest.raises(DuplicatePaymentError):
        repository.save(make_payment("txn_dup"))


def test_payments_without_a_key_never_collide(repository):
    repository.save(make_payment("txn_x"))
    repository.save(make_payment("txn_y"))

    assert repository.get("txn_x") is not None
    assert repository.get("txn_y") is not None


def test_only_one_of_many_concurrent_saves_with_one_key_wins(repository):
    def save(index: int) -> bool:
        try:
            repository.save(make_payment(f"txn_race_{index}", key="race"))
            return True
        except DuplicateIdempotencyKeyError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(save, range(8)))

    assert results.count(True) == 1


# Behaviour specific to SQLite: a file shared by several workers.


def test_sqlite_payments_survive_reopening_the_file(tmp_path):
    path = tmp_path / "p.db"
    SqlitePaymentRepository(path).save(make_payment("txn_5", key="k5"))

    reopened = SqlitePaymentRepository(path)

    assert reopened.get("txn_5") is not None
    assert reopened.get_by_key("k5").record.transaction_id == "txn_5"


def test_sqlite_workers_sharing_a_file_agree_on_one_key(tmp_path):
    path = tmp_path / "p.db"
    first_worker = SqlitePaymentRepository(path)
    second_worker = SqlitePaymentRepository(path)
    first_worker.save(make_payment("txn_a", key="same"))

    with pytest.raises(DuplicateIdempotencyKeyError):
        second_worker.save(make_payment("txn_b", key="same"))

    assert second_worker.get_by_key("same").record.transaction_id == "txn_a"


def test_concurrent_requests_through_separate_workers_create_one_payment(tmp_path):
    path = tmp_path / "p.db"
    services = [build_payment_service(SqlitePaymentRepository(path)) for _ in range(8)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda s: s.create(make_request(), "race-key"), services))

    assert len({outcome.record.transaction_id for outcome in outcomes}) == 1
    assert sum(1 for outcome in outcomes if not outcome.replayed) == 1
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 1


def test_concurrent_requests_with_one_key_and_different_bodies_conflict(tmp_path):
    path = tmp_path / "p.db"
    services = [build_payment_service(SqlitePaymentRepository(path)) for _ in range(6)]

    def submit(args):
        service, reference = args
        try:
            return service.create(make_request(reference=reference), "conflict-key")
        except IdempotencyConflictError:
            return "conflict"

    jobs = [(service, f"order_{i}") for i, service in enumerate(services)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        outcomes = list(pool.map(submit, jobs))

    created = [o for o in outcomes if o != "conflict" and not o.replayed]
    assert len(created) == 1
    assert outcomes.count("conflict") == 5
