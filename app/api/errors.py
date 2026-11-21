"""Error-body construction and exception->HTTP mapping (api-contracts §2.1).

Registered on the FastAPI app in app/main.py so every route raises plain
domain exceptions and gets the exact contract error body back, instead
of each route hand-rolling JSONResponse objects.
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from app.actions.errors import ActionConflict, ActionExpired, ActionNotAccessible
from app.contracts.schemas import ErrorBody, ErrorDetail
from app.privacy.errors import ResourceNotAccessible, Unauthenticated


class BadRequest(Exception):
    """Validation failure the route detected itself (e.g. an unregistered
    settings_changes key, api-contracts §5.2). -> HTTP 400."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def error_response(status_code: int, code: str, message: str, trace_id: str | None = None) -> JSONResponse:
    body = ErrorBody(error=ErrorDetail(code=code, message=message, trace_id=trace_id))
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def register_exception_handlers(app) -> None:
    @app.exception_handler(BadRequest)
    def _bad_request(request: Request, exc: BadRequest) -> JSONResponse:
        return error_response(400, "bad_request", exc.message)

    @app.exception_handler(Unauthenticated)
    def _unauthenticated(request: Request, exc: Unauthenticated) -> JSONResponse:
        return error_response(401, "unauthenticated", "Missing or unknown X-Passenger-Id.")

    @app.exception_handler(ResourceNotAccessible)
    def _not_accessible(request: Request, exc: ResourceNotAccessible) -> JSONResponse:
        return error_response(404, "not_found", "Not found.")

    @app.exception_handler(ActionNotAccessible)
    def _action_not_accessible(request: Request, exc: ActionNotAccessible) -> JSONResponse:
        return error_response(404, "not_found", "Not found.")

    @app.exception_handler(ActionConflict)
    def _action_conflict(request: Request, exc: ActionConflict) -> JSONResponse:
        return error_response(409, "conflict", "This action is not in a state that allows that.")

    @app.exception_handler(ActionExpired)
    def _action_expired(request: Request, exc: ActionExpired) -> JSONResponse:
        return error_response(410, "expired", "This request has expired.")
