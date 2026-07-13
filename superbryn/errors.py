"""Typed errors for the SuperBryn SDK.

Every non-2xx API response maps to a concrete subclass of
:class:`SuperbrynAPIError` so callers can catch exactly what they care
about (e.g. retry on :class:`RateLimitError`, fail the deploy on
:class:`ManifestValidationError`).
"""

from __future__ import annotations

from typing import Any


class SuperbrynError(Exception):
    """Base class for every error raised by this SDK."""


class ConfigurationError(SuperbrynError):
    """Client-side misconfiguration (missing API key / base URL)."""


class AmbiguousScanError(SuperbrynError, ValueError):
    """A source scan found multiple competing candidates for a field.

    Raised instead of silently guessing (e.g. two long prompt strings in
    different files). Narrow the scan to the specific agent file, or pass
    ``on_ambiguity="longest"`` to accept the previous longest-wins behavior.
    """

    def __init__(self, field_name: str, candidates: list[tuple[str, str]]):
        self.field_name = field_name
        self.candidates = candidates
        locations = ", ".join(sorted({file for file, _ in candidates}))
        super().__init__(
            f"source scan found {len(candidates)} competing values for {field_name!r} "
            f"(in: {locations}). Scan the specific agent file instead of the whole "
            f'project, or pass on_ambiguity="longest" to pick the longest one.'
        )


class SuperbrynAPIError(SuperbrynError):
    """Non-2xx response from the SuperBryn API."""

    def __init__(self, status: int, body: Any = None, message: str | None = None):
        self.status = status
        self.body = body
        super().__init__(message or f"SuperBryn API error (HTTP {status}): {body}")


class AuthenticationError(SuperbrynAPIError):
    """401 — missing, invalid, or revoked API key."""


class ScopeError(SuperbrynAPIError):
    """403 — the key is not agent-scoped (sync requires an agent key)."""


class NotFoundError(SuperbrynAPIError):
    """404 — no live version / no pending draft."""


class ManifestValidationError(SuperbrynAPIError):
    """400 — the manifest failed schema validation (unknown keys / wrong types)."""

    @property
    def details(self) -> list[dict[str, Any]]:
        if isinstance(self.body, dict):
            return self.body.get("details") or []
        return []


class BusinessRuleError(SuperbrynAPIError):
    """422 — the manifest violates a semantic rule (E.164, BCP-47, ranges...)."""

    @property
    def details(self) -> list[dict[str, Any]]:
        if isinstance(self.body, dict):
            return self.body.get("details") or []
        return []


class RateLimitError(SuperbrynAPIError):
    """429 — per-key rate limit exceeded; retry with backoff."""


def error_for_status(status: int, body: Any) -> SuperbrynAPIError:
    """Map an HTTP status to the concrete error class."""
    cls: type[SuperbrynAPIError]
    if status == 400:
        cls = ManifestValidationError
    elif status == 401:
        cls = AuthenticationError
    elif status == 403:
        cls = ScopeError
    elif status == 404:
        cls = NotFoundError
    elif status == 422:
        cls = BusinessRuleError
    elif status == 429:
        cls = RateLimitError
    else:
        cls = SuperbrynAPIError
    return cls(status, body)
