"""FastAPI app + router wiring (api-contracts §4).

SHARED-FROZEN (architecture §8). Phase 0 wires the contract-valid fakes
from tests/fakes/ behind app.state so every route already matches the
real interfaces in app/contracts/interfaces.py; Phase 1 swaps each fake
for its real implementation without touching the routers.
"""
from __future__ import annotations

from fastapi import FastAPI

from app.api import actions, bookings, chat, health, ingest, trace
from app.api.errors import register_exception_handlers
from app.llm.orchestrator import RealOrchestrator
from tests.fakes.action_service import FakeActionService
from tests.fakes.clock import FakeClock
from tests.fakes.handoff_service import FakeHandoffService
from tests.fakes.retriever import FakeRetriever
from tests.fakes.session_store import FakeSessionStore
from tests.fakes.tool_registry import FakeToolRegistry


def create_app(db_path: str | None = None) -> FastAPI:
    """`db_path` lets callers (tests) point at an isolated file instead
    of the configured default — the app's own routes still use the
    Phase 0 fakes above; only the real DB init/health check (app/db/)
    reads this path for now."""
    app = FastAPI(title="Ujjwal Rail — Phase 0 skeleton")

    from app.config import settings
    from app.db.connection import init_db

    # Initialized ONCE here, at app creation — never per request.
    app.state.db_path = db_path if db_path is not None else settings.db_path
    init_db(app.state.db_path).close()

    clock = FakeClock()
    app.state.clock = clock
    app.state.tool_registry = FakeToolRegistry()
    app.state.retriever = FakeRetriever()
    app.state.action_service = FakeActionService(clock)
    app.state.handoff_service = FakeHandoffService(clock)
    app.state.session_store = FakeSessionStore()
    # RealOrchestrator (app/llm/orchestrator.py): routes to the real,
    # SQLite-backed tools (app/tools/) and RAG (app/rag/) built in prior
    # phases. It opens its own DB connection per call via this getter,
    # so it always reads app.state.db_path as currently set — not a
    # value captured once at startup.
    app.state.orchestrator = RealOrchestrator(
        db_path_getter=lambda: app.state.db_path,
        clock=clock,
        action_service=app.state.action_service,
        handoff_service=app.state.handoff_service,
    )

    from app.audit.store import InMemoryTraceStore

    app.state.trace_store = InMemoryTraceStore()

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(actions.router)
    app.include_router(bookings.router)
    app.include_router(ingest.router)
    app.include_router(trace.router)

    return app


app = create_app()
