"""Typed errors for the action lifecycle (docs/api-contracts.md §2.1, §9).

Real ActionService implementations (Backend, Phase 1) and the stub
ActionService used in Phase 0 both raise these; `app/api` maps them to
the exact HTTP status/body the contract specifies. Kept here, not in
tests/fakes/, because the shape is part of the contract, not a fake-only
detail.
"""
from __future__ import annotations


class ActionNotAccessible(Exception):
    """Action is missing, or belongs to a different passenger — the two
    cases are made indistinguishable on purpose (R8). -> HTTP 404."""


class ActionConflict(Exception):
    """Action is not in a state that allows this call (e.g. cancel after
    confirm; or already cancelled). -> HTTP 409."""


class ActionExpired(Exception):
    """Clock.now_utc() >= action.expires_at (D6: operational clock only,
    never as_of). -> HTTP 410."""
