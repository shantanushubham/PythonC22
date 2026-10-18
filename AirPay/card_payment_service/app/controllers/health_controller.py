"""Liveness endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.container import get_network_registry
from app.networks import NetworkRegistry
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    operation_id="getHealth",
    summary="Check the service is running",
    response_model=HealthResponse,
)
def health(
    registry: Annotated[NetworkRegistry, Depends(get_network_registry)],
) -> HealthResponse:
    return HealthResponse(networks=registry.networks)
