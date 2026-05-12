from typing import Any
from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse

from dashboard.backend.app import (
    api_runs,
    api_run,
    api_run_prompt_copies,
    api_run_update_prompt_copies,
    api_edit_prompt,
    api_delete_prompt,
    api_delete_image,
    api_download_single_image,
    api_download_batch_images,
    api_download_batches,
)

router = APIRouter()

@router.get("/api/runs")
def _runs() -> dict[str, Any]:
    return api_runs()

@router.get("/api/runs/{run_id}")
def _run(run_id: str) -> dict[str, Any]:
    return api_run(run_id)

@router.get("/api/runs/{run_id}/prompt-copies")
def _prompt_copies(run_id: str) -> dict[str, Any]:
    return api_run_prompt_copies(run_id)

@router.post("/api/runs/{run_id}/prompt-copies")
def _update_prompt_copies(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return api_run_update_prompt_copies(run_id, payload)

@router.post("/api/runs/{run_id}/edit-prompt")
def _edit_prompt(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return api_edit_prompt(run_id, payload)

@router.post("/api/runs/{run_id}/delete-prompt")
def _delete_prompt(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return api_delete_prompt(run_id, payload)

@router.post("/api/runs/{run_id}/delete-image")
def _delete_image(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return api_delete_image(run_id, payload)

@router.get("/api/runs/{run_id}/download-image")
def _download_single_image(run_id: str, image_file: str) -> StreamingResponse:
    return api_download_single_image(run_id, image_file)

@router.get("/api/runs/{run_id}/download-batch")
def _download_batch_images(run_id: str) -> StreamingResponse:
    return api_download_batch_images(run_id)


@router.post("/api/runs/download-batches")
def _download_batches(payload: dict[str, Any] = Body(...)) -> StreamingResponse:
    return api_download_batches(payload.get("batch_ids", []))
