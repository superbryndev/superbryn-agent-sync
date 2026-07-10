import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from superbryn import (
    AuthenticationError,
    BusinessRuleError,
    ConfigurationError,
    Manifest,
    ManifestValidationError,
    RateLimitError,
    ScopeError,
    Superbryn,
    compute_manifest_hash,
)

# ── local stub server ────────────────────────────────────────────────────────

# Hash covers the config block only, so fixtures must differ under config.
LIVE_MANIFEST = {
    "llm": {"provider": "openai", "model": "gpt-4o"},
    "config": {"identity": {"name": "Live Agent"}},
}
LIVE_HASH = compute_manifest_hash(LIVE_MANIFEST)


class StubHandler(BaseHTTPRequestHandler):
    requests: list[dict] = []

    def _respond(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _record(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length)) if length else None
        record = {
            "method": self.command,
            "path": self.path,
            "api_key": self.headers.get("X-API-Key"),
            "body": body,
        }
        StubHandler.requests.append(record)
        return record

    def do_POST(self):  # noqa: N802
        record = self._record()
        key = record["api_key"]
        if key == "bad":
            return self._respond(401, {"error": "unauthorized"})
        if key == "org-key":
            return self._respond(403, {"error": "key_missing_agent_scope"})
        if key == "limited":
            return self._respond(429, {"error": "RATE_LIMITED"})
        body = record["body"] or {}
        if "confg" in body:
            return self._respond(400, {"error": "VALIDATION_ERROR", "details": [{"path": "confg"}]})
        phone = ((body.get("config") or {}).get("telephony") or {}).get("phone_number")
        if phone == "555-1234":
            return self._respond(
                422,
                {
                    "error": "BUSINESS_RULE_VIOLATION",
                    "details": [{"path": "config.telephony.phone_number"}],
                },
            )
        if compute_manifest_hash(body) == LIVE_HASH:
            return self._respond(
                200, {"agent_row_id": "row-1", "status": "noop", "hash": LIVE_HASH}
            )
        return self._respond(
            201,
            {
                "agent_row_id": "row-2",
                "approval_status": "pending",
                "verification_status": "pending",
                "hash": compute_manifest_hash(body),
                "change_types": ["llm_provider"],
            },
        )

    def log_message(self, *args):  # silence stub server logging
        pass


@pytest.fixture(scope="module")
def stub_url():
    server = HTTPServer(("127.0.0.1", 0), StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


# ── tests ────────────────────────────────────────────────────────────────────


def test_missing_api_key_raises_configuration_error(monkeypatch):
    monkeypatch.delenv("SUPERBRYN_API_KEY", raising=False)
    with pytest.raises(ConfigurationError):
        Superbryn()


def test_sync_creates_draft(stub_url):
    client = Superbryn(api_key="good", base_url=stub_url)
    manifest = (
        Manifest.builder()
        .set_llm(provider="anthropic", model="claude-sonnet-4-5")
        .set_identity(name="New Agent")
        .build()
    )
    result = client.sync(manifest)
    assert result["approval_status"] == "pending"
    assert result["change_types"] == ["llm_provider"]


def test_sync_noop_when_hash_matches_live(stub_url):
    client = Superbryn(api_key="good", base_url=stub_url)
    result = client.sync(dict(LIVE_MANIFEST))
    assert result["status"] == "noop"
    assert result["hash"] == LIVE_HASH


def test_error_mapping(stub_url):
    manifest = {"llm": {"provider": "x"}}
    with pytest.raises(AuthenticationError):
        Superbryn(api_key="bad", base_url=stub_url).sync(manifest)
    with pytest.raises(ScopeError):
        Superbryn(api_key="org-key", base_url=stub_url).sync(manifest)
    with pytest.raises(RateLimitError):
        Superbryn(api_key="limited", base_url=stub_url).sync(manifest)

    with pytest.raises(ManifestValidationError) as exc_info:
        Superbryn(api_key="good", base_url=stub_url).sync({"confg": {}})
    assert exc_info.value.details == [{"path": "confg"}]

    bad_phone = {"config": {"telephony": {"phone_number": "555-1234"}}}
    with pytest.raises(BusinessRuleError) as exc_info:
        Superbryn(api_key="good", base_url=stub_url).sync(bad_phone)
    assert exc_info.value.details[0]["path"] == "config.telephony.phone_number"
