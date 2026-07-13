"""AsyncSuperbryn against a real local aiohttp server, plus timeout behavior."""

from __future__ import annotations

import asyncio
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from superbryn import AuthenticationError, ConfigurationError, Superbryn

aiohttp = pytest.importorskip("aiohttp")
from aiohttp import web  # noqa: E402

from superbryn import AsyncSuperbryn  # noqa: E402

ACCEPTED = {
    "agent_row_id": "row-1",
    "approval_status": "pending",
    "hash": "abc",
    "change_types": ["llm"],
}


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _serve(handler):
    app = web.Application()
    app.router.add_post("/public-api/v1/agents/me/sync", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, f"http://127.0.0.1:{port}"


def test_async_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("SUPERBRYN_API_KEY", raising=False)
    with pytest.raises(ConfigurationError):
        AsyncSuperbryn()


def test_async_sync_success_and_headers():
    async def scenario():
        seen = {}

        async def handler(request):
            seen["api_key"] = request.headers.get("X-API-Key")
            seen["body"] = await request.json()
            return web.json_response(ACCEPTED)

        runner, base_url = await _serve(handler)
        try:
            client = AsyncSuperbryn(api_key="sk_agent_x", base_url=base_url)
            result = await client.sync({"source": "custom"})
        finally:
            await runner.cleanup()
        return seen, result

    seen, result = _run(scenario())
    assert result == ACCEPTED
    assert seen["api_key"] == "sk_agent_x"
    assert seen["body"] == {"source": "custom"}


def test_async_sync_maps_http_errors():
    async def scenario():
        async def handler(request):
            return web.json_response({"error": "bad key"}, status=401)

        runner, base_url = await _serve(handler)
        try:
            client = AsyncSuperbryn(api_key="sk_agent_x", base_url=base_url)
            with pytest.raises(AuthenticationError) as excinfo:
                await client.sync({"source": "custom"})
        finally:
            await runner.cleanup()
        return excinfo.value

    error = _run(scenario())
    assert error.status == 401


def test_async_sync_timeout():
    async def scenario():
        async def handler(request):
            await asyncio.sleep(5)
            return web.json_response(ACCEPTED)

        runner, base_url = await _serve(handler)
        try:
            client = AsyncSuperbryn(api_key="sk_agent_x", base_url=base_url, timeout=0.2)
            with pytest.raises(asyncio.TimeoutError):
                await client.sync({"source": "custom"})
        finally:
            await runner.cleanup()

    _run(scenario())


# ── blocking client timeout (stdlib server that stalls) ──────────────────


class _StallingHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        time.sleep(5)

    def log_message(self, *args):
        pass


def test_blocking_sync_timeout():
    server = HTTPServer(("127.0.0.1", 0), _StallingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = Superbryn(
            api_key="sk_agent_x",
            base_url=f"http://127.0.0.1:{server.server_port}",
            timeout=0.2,
        )
        with pytest.raises((TimeoutError, socket.timeout, OSError)):
            client.sync({"source": "custom"})
    finally:
        server.shutdown()
        server.server_close()
