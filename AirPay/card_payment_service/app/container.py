"""Composition root: the one place that chooses concrete classes.

Everything else depends on abstractions. To change the database, the decline scenarios,
or the supported networks, change them here. Tests replace any of these with
`app.dependency_overrides`.
"""

from collections.abc import Sequence
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.config import Settings, load_settings
from app.mappers import PaymentMapper
from app.networks import NetworkRegistry, default_registry
from app.repositories.payment_repository import PaymentReader, PaymentRepository
from app.repositories.sqlite_payment_repository import SqlitePaymentRepository
from app.services.card_validation_service import CardValidationService
from app.services.idempotency_service import IdempotencyService
from app.services.issuer_decision_service import (
    DeclineRule,
    IssuerDecisionService,
    default_decline_rules,
)
from app.services.payment_query_service import PaymentQueryService
from app.services.payment_service import PaymentService


@lru_cache
def get_settings() -> Settings:
    return load_settings()


@lru_cache
def get_network_registry() -> NetworkRegistry:
    return default_registry()


@lru_cache
def get_payment_repository() -> PaymentRepository:
    # Opened on the first request, not at import time.
    return SqlitePaymentRepository(get_settings().db_path)


def build_payment_service(
    repository: PaymentRepository,
    registry: NetworkRegistry | None = None,
    decline_rules: Sequence[DeclineRule] | None = None,
) -> PaymentService:
    return PaymentService(
        repository=repository,
        card_validation=CardValidationService(registry or default_registry()),
        issuer=IssuerDecisionService(
            decline_rules if decline_rules is not None else default_decline_rules()
        ),
        idempotency=IdempotencyService(),
        mapper=PaymentMapper(),
    )


def get_payment_service(
    repository: Annotated[PaymentRepository, Depends(get_payment_repository)],
    registry: Annotated[NetworkRegistry, Depends(get_network_registry)],
) -> PaymentService:
    return build_payment_service(repository, registry)


def get_payment_query_service(
    reader: Annotated[PaymentReader, Depends(get_payment_repository)],
) -> PaymentQueryService:
    return PaymentQueryService(reader)
