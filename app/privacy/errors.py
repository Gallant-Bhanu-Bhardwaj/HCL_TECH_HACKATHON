"""Typed privacy/auth errors (docs/api-contracts.md §2.1, §12)."""
from __future__ import annotations


class Unauthenticated(Exception):
    """Missing or unknown X-Passenger-Id. -> HTTP 401."""


class ResourceNotAccessible(Exception):
    """Resource is missing, or belongs to a different passenger — made
    indistinguishable on purpose (R8). -> HTTP 404."""
