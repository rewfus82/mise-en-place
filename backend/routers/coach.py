from __future__ import annotations

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from backend.schemas.coach import CoachAskRequest
from backend.services import coach_service

router = APIRouter(tags=["coach"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


@router.post("/ask")
async def ask(
    req: CoachAskRequest,
    x_llm_provider: str = Header(default=""),
    x_llm_key: str = Header(default=""),
):
    """Stream a cited, sourced answer to a nutrition question."""

    async def generator():
        async for chunk in coach_service.ask_stream(
            req.question, x_llm_provider, x_llm_key
        ):
            yield chunk

    return StreamingResponse(
        generator(), media_type="text/event-stream", headers=_SSE_HEADERS
    )
