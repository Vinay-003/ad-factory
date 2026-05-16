from typing import Any
from fastapi import APIRouter, Body

from dashboard.backend.app import (
    api_defaults,
    api_delete_input_image,
    api_opencode_catalog,
    api_product_doc,
    api_save_product_doc,
    api_prompt_file_content,
    api_save_prompt_file_content,
)

router = APIRouter()

@router.get("/api/defaults")
def _defaults() -> dict[str, Any]:
    return api_defaults()

@router.get("/api/opencode/catalog")
def _opencode_catalog() -> dict[str, Any]:
    return api_opencode_catalog()

@router.delete("/api/input-images")
def _delete_input_image(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return api_delete_input_image(payload)

@router.get("/api/product-doc")
def _product_doc() -> dict[str, Any]:
    return api_product_doc()

@router.post("/api/product-doc")
def _save_product_doc(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return api_save_product_doc(payload)

@router.get("/api/prompt-file-content")
def _prompt_file_content(prompt_path: str = "") -> dict[str, Any]:
    return api_prompt_file_content(prompt_path)

@router.post("/api/prompt-file-content")
def _save_prompt_file_content(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return api_save_prompt_file_content(payload)
