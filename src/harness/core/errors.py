"""Typed error taxonomy mapped to structured API responses."""

from __future__ import annotations


class HarnessError(Exception):
    """Base error. ``code`` is stable and machine-readable; ``status`` is the HTTP mapping."""

    code = "internal_error"
    status = 500

    def __init__(self, message: str, *, detail: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


class NotFoundError(HarnessError):
    code = "not_found"
    status = 404


class ValidationFailedError(HarnessError):
    code = "validation_failed"
    status = 422


class ConflictError(HarnessError):
    code = "conflict"
    status = 409


class AuthRequiredError(HarnessError):
    code = "auth_required"
    status = 401


class PermissionDeniedError(HarnessError):
    code = "permission_denied"
    status = 403


class ProviderError(HarnessError):
    """A provider/engine adapter failed; never crashes the server (SPEC/ARCHITECTURE.md)."""

    code = "provider_error"
    status = 502


class UnsupportedCapabilityError(HarnessError):
    """An adapter was asked for a capability it explicitly does not support."""

    code = "unsupported_capability"
    status = 501


class BudgetExceededError(HarnessError):
    code = "context_budget_exceeded"
    status = 422
