"""GET /health (api-contracts §4.6)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_retriever
from app.config import settings
from app.contracts.schemas import HealthResponse
from app.db.connection import check_connectivity

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(request: Request, retriever=Depends(get_retriever)) -> HealthResponse:
    stats = retriever.stats()
    db_ok = check_connectivity(request.app.state.db_path)
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        db="ok" if db_ok else "unreachable",
        index_docs=stats.get("docs", 0),
        llm="mock" if settings.mock_llm else "ollama",
        mock_llm=settings.mock_llm,
    )
