from typing import Any
from fastapi import APIRouter

from dashboard.backend.app import (
    api_defaults,
    api_opencode_catalog,
)

router = APIRouter()

@router.get("/api/defaults")
def _defaults() -> dict[str, Any]:
    return api_defaults()

@router.get("/api/opencode/catalog")
def _opencode_catalog() -> dict[str, Any]:
    return api_opencode_catalog()
