"""AgentSyncManifest builder.

Builder methods mirror the grouped ``config`` sections of the canonical
manifest so setting a value promotes the correct ``change_type`` at diff
time on the server. Every field is optional — an empty manifest is valid.

The bundled JSON Schema lives at
``superbryn/schemas/agent_sync_manifest.schema.json`` (see
:func:`load_manifest_schema`).
"""

from __future__ import annotations

import importlib.resources
import json
from typing import Any

from .canonical import compute_manifest_hash

SYNC_SOURCES = (
    "pipecat",
    "livekit",
    "vapi",
    "retell",
    "elevenlabs",
    "bland",
    "bolna",
    "hooman-labs",
    "shunya-labs",
    "custom",
)


def load_manifest_schema() -> dict[str, Any]:
    """Return the bundled AgentSyncManifest JSON Schema as a dict."""
    ref = importlib.resources.files("superbryn.schemas") / "agent_sync_manifest.schema.json"
    return json.loads(ref.read_text(encoding="utf-8"))


def _clean(mapping: dict[str, Any]) -> dict[str, Any]:
    """Drop keys whose value is the ``_UNSET`` sentinel (keep explicit None)."""
    return {k: v for k, v in mapping.items() if v is not _UNSET}


_UNSET = object()


class Manifest(dict):
    """A built AgentSyncManifest. A plain ``dict`` subclass — JSON-ready."""

    @classmethod
    def builder(cls, source: str = "custom") -> ManifestBuilder:
        return ManifestBuilder(source=source)

    @property
    def hash(self) -> str:
        """Client-side content hash (matches the server's ``__meta.hash``)."""
        return compute_manifest_hash(self)


class ManifestBuilder:
    """Fluent builder for :class:`Manifest`.

    Only sections you set are included in the built manifest. Passing
    ``None`` for a nullable field sends an explicit null (unset on the
    server); omitting the argument leaves the field out entirely.
    """

    def __init__(self, source: str = "custom"):
        if source not in SYNC_SOURCES:
            raise ValueError(f"source must be one of {SYNC_SOURCES}, got {source!r}")
        self._manifest: dict[str, Any] = {"source": source}
        self._config: dict[str, Any] = {}
        self._tools: list[dict[str, Any]] = []

    # ── envelope ─────────────────────────────────────────────────────────

    def set_source_agent_id(self, source_agent_id: str) -> ManifestBuilder:
        self._manifest["source_agent_id"] = source_agent_id
        return self

    # ── runtime pipeline (top-level) ─────────────────────────────────────

    def set_llm(
        self,
        provider: Any = _UNSET,
        model: Any = _UNSET,
        temperature: Any = _UNSET,
        max_tokens: Any = _UNSET,
        fallback: Any = _UNSET,
        extra: Any = _UNSET,
    ) -> ManifestBuilder:
        self._manifest["llm"] = _clean(
            {
                "provider": provider,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "fallback": fallback,
                "extra": extra,
            }
        )
        return self

    def set_stt(
        self,
        provider: Any = _UNSET,
        model: Any = _UNSET,
        language: Any = _UNSET,
        fallback: Any = _UNSET,
        extra: Any = _UNSET,
    ) -> ManifestBuilder:
        self._manifest["stt"] = _clean(
            {
                "provider": provider,
                "model": model,
                "language": language,
                "fallback": fallback,
                "extra": extra,
            }
        )
        return self

    def set_tts(
        self,
        provider: Any = _UNSET,
        voice_id: Any = _UNSET,
        model: Any = _UNSET,
        fallback: Any = _UNSET,
        extra: Any = _UNSET,
    ) -> ManifestBuilder:
        self._manifest["tts"] = _clean(
            {
                "provider": provider,
                "voice_id": voice_id,
                "model": model,
                "fallback": fallback,
                "extra": extra,
            }
        )
        return self

    def set_voice(
        self,
        provider: Any = _UNSET,
        voice_id: Any = _UNSET,
        style: Any = _UNSET,
        fallback: Any = _UNSET,
        extra: Any = _UNSET,
    ) -> ManifestBuilder:
        self._manifest["voice"] = _clean(
            {
                "provider": provider,
                "voice_id": voice_id,
                "style": style,
                "fallback": fallback,
                "extra": extra,
            }
        )
        return self

    # ── config groups ────────────────────────────────────────────────────

    def set_identity(
        self,
        name: Any = _UNSET,
        type: Any = _UNSET,  # noqa: A002 — mirrors the wire field name
        agent_modality: Any = _UNSET,
        description: Any = _UNSET,
        pain_point: Any = _UNSET,
        gender: Any = _UNSET,
        age: Any = _UNSET,
        dob: Any = _UNSET,
    ) -> ManifestBuilder:
        self._config["identity"] = _clean(
            {
                "name": name,
                "type": type,
                "agent_modality": agent_modality,
                "description": description,
                "pain_point": pain_point,
                "gender": gender,
                "age": age,
                "dob": dob,
            }
        )
        return self

    def set_behavior(self, prompt: Any = _UNSET, flow: Any = _UNSET) -> ManifestBuilder:
        self._config["behavior"] = _clean({"prompt": prompt, "flow": flow})
        return self

    def add_tool(
        self,
        name: Any = _UNSET,
        description: Any = _UNSET,
        schema: Any = _UNSET,
        server: Any = _UNSET,
    ) -> ManifestBuilder:
        self._tools.append(
            _clean({"name": name, "description": description, "schema": schema, "server": server})
        )
        return self

    def set_language(
        self, primary_language: Any = _UNSET, additional_languages: Any = _UNSET
    ) -> ManifestBuilder:
        self._config["language"] = _clean(
            {"primary_language": primary_language, "additional_languages": additional_languages}
        )
        return self

    def set_telephony(
        self, phone_number: Any = _UNSET, ivr_config: Any = _UNSET
    ) -> ManifestBuilder:
        self._config["telephony"] = _clean({"phone_number": phone_number, "ivr_config": ivr_config})
        return self

    def set_additional_details(self, additional_details: str | None) -> ManifestBuilder:
        self._config["additional_details"] = additional_details
        return self

    def set_policy_guardrails(self, policy_guardrails: str | None) -> ManifestBuilder:
        self._config["policy_guardrails"] = policy_guardrails
        return self

    def set_concurrency_calls(self, concurrency_calls: int) -> ManifestBuilder:
        self._config["concurrency_calls"] = concurrency_calls
        return self

    # ── build ────────────────────────────────────────────────────────────

    def build(self) -> Manifest:
        manifest = dict(self._manifest)
        config = dict(self._config)
        if self._tools:
            config["tools"] = list(self._tools)
        if config:
            manifest["config"] = config
        return Manifest(manifest)
