"""SuperBryn API client for agent config sync.

Zero runtime dependencies — the blocking path uses stdlib ``urllib``.
An async variant is available when ``aiohttp`` is installed
(``pip install superbryn-agent-sync[async]``).

Requires an **agent-scoped** API key (created against a single agent in
the SuperBryn dashboard); org-scoped keys are rejected. A pushed
manifest lands as a pending draft that a human approves in the review
UI — syncing never changes the live agent directly.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from .__about__ import __version__
from .errors import ConfigurationError, error_for_status

logger = logging.getLogger("superbryn")

DEFAULT_BASE_URL = "https://api.superbryn.com"
SYNC_PATH = "/public-api/v1/agents/me/sync"

_USER_AGENT = f"superbryn-python/{__version__}"


class Superbryn:
    """Client for the SuperBryn agent-sync API.

    >>> from superbryn import Superbryn, Manifest
    >>> manifest = Manifest.builder(source="custom").set_identity(name="Support Agent").build()
    >>> Superbryn(api_key="sk_agent_...").sync(manifest)
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ):
        self.api_key = api_key or os.getenv("SUPERBRYN_API_KEY") or ""
        self.base_url = (base_url or os.getenv("SUPERBRYN_BASE_URL") or DEFAULT_BASE_URL).rstrip(
            "/"
        )
        self.timeout = timeout
        if not self.api_key:
            raise ConfigurationError(
                "SuperBryn API key missing — pass api_key= or set SUPERBRYN_API_KEY"
            )

    # ── public surface ───────────────────────────────────────────────────

    def sync(self, manifest: dict[str, Any]) -> dict[str, Any]:
        """Push a manifest. Lands as a pending draft (or a no-op)."""
        result = self._request("POST", SYNC_PATH, body=dict(manifest))
        logger.info(
            "superbryn.sync: %s (hash=%s)",
            result.get("status") or result.get("approval_status"),
            result.get("hash"),
        )
        return result

    # ── transport ────────────────────────────────────────────────────────

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = self.base_url + path
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": self.api_key,
                "User-Agent": _USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed: Any = json.loads(raw)
            except ValueError:
                parsed = raw
            raise error_for_status(exc.code, parsed) from None


class AsyncSuperbryn:
    """Async client (requires ``aiohttp`` — ``pip install superbryn-agent-sync[async]``)."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ):
        self.api_key = api_key or os.getenv("SUPERBRYN_API_KEY") or ""
        self.base_url = (base_url or os.getenv("SUPERBRYN_BASE_URL") or DEFAULT_BASE_URL).rstrip(
            "/"
        )
        self.timeout = timeout
        if not self.api_key:
            raise ConfigurationError(
                "SuperBryn API key missing — pass api_key= or set SUPERBRYN_API_KEY"
            )

    async def sync(self, manifest: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", SYNC_PATH, body=dict(manifest))

    async def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        import aiohttp  # lazy — optional extra

        url = self.base_url + path
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
            "User-Agent": _USER_AGENT,
        }
        client_timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.request(method, url, json=body, headers=headers) as response:
                try:
                    payload: Any = await response.json()
                except Exception:  # noqa: BLE001
                    payload = await response.text()
                if response.status >= 400:
                    raise error_for_status(response.status, payload)
                return payload
