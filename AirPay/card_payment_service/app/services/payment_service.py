"""Authorizes a card payment by coordinating the other services.

This class makes no decisions of its own. Validation, the issuer decision, idempotency
rules, record building, and storage each live in their own class and are passed in
(Dependency Inversion). It only runs them in order.
"""

import logging
from dataclasses import dataclass

from app.mappers import PaymentMapper
from app.models import PaymentRecord
from app.repositories.payment_repository import (
    DuplicateIdempotencyKeyError,
    PaymentRepository,
    StoredPayment,
)
from app.schemas import CreatePaymentRequest
from app.services.card_validation_service import CardValidationService
from app.services.idempotency_service import IdempotencyService
from app.services.issuer_decision_service import AuthorizationAttempt, IssuerDecisionService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessedPayment:
    record: PaymentRecord
    replayed: bool = False


class PaymentService:
    def __init__(
        self,
        repository: PaymentRepository,
        card_validation: CardValidationService,
        issuer: IssuerDecisionService,
        idempotency: IdempotencyService,
        mapper: PaymentMapper,
    ) -> None:
        self._repository = repository
        self._card_validation = card_validation
        self._issuer = issuer
        self._idempotency = idempotency
        self._mapper = mapper

    def create(
        self,
        request: CreatePaymentRequest,
        idempotency_key: str | None,
    ) -> ProcessedPayment:
        key = self._idempotency.clean_key(idempotency_key)
        fingerprint = self._idempotency.fingerprint(request)

        # Fast path: the key was already used, so replay without validating again.
        if key is not None:
            stored = self._repository.get_by_key(key)
            if stored is not None:
                return self._replay(stored, fingerprint)

        card = self._card_validation.validate(request)
        decision = self._issuer.decide(
            AuthorizationAttempt(pan=card.pan, cvv=request.card.cvv, amount=request.amount)
        )
        record = self._mapper.to_record(request, card, decision)

        try:
            self._repository.save(
                StoredPayment(record=record, fingerprint=fingerprint, idempotency_key=key)
            )
        except DuplicateIdempotencyKeyError:
            # Another request, possibly in another worker, saved this key between our
            # check and our save. The repository picked the winner, so replay it.
            winner = self._repository.get_by_key(key) if key is not None else None
            if winner is None:
                raise
            return self._replay(winner, fingerprint)

        logger.info(
            "payment_processed transaction_id=%s status=%s network=%s last4=%s",
            record.transaction_id,
            record.status,
            record.card.network.value,
            record.card.last4,
        )
        return ProcessedPayment(record=record)

    def _replay(self, stored: StoredPayment, fingerprint: str) -> ProcessedPayment:
        self._idempotency.ensure_same_request(stored, fingerprint)
        logger.info(
            "payment_replayed transaction_id=%s status=%s",
            stored.record.transaction_id,
            stored.record.status,
        )
        return ProcessedPayment(record=stored.record, replayed=True)
