"""Web UI routes for TTS Adapter."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from .templates import INDEX_HTML

router = APIRouter(tags=["web"])


@router.get("/", response_class=HTMLResponse)
def web_ui() -> str:
    """Serve web UI for TTS generation."""
    return INDEX_HTML
