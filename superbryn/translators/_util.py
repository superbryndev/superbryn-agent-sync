"""Shared helpers for provider translators."""

from __future__ import annotations

from typing import Any

from ..manifest import Manifest


def get_path(source: Any, *path: str) -> Any:
    """Nested dict lookup that never raises; returns None on any miss."""
    cur = source
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def clean_block(block: dict[str, Any]) -> dict[str, Any] | None:
    """Drop None values; return None when nothing survives."""
    cleaned = {k: v for k, v in block.items() if v is not None}
    return cleaned or None


def normalize_tools(tools: Any) -> list[dict[str, Any]] | None:
    """Map provider tool lists into manifest tool entries (best effort)."""
    if not isinstance(tools, list) or not tools:
        return None
    out: list[dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        # Providers wrap function tools differently; check common shapes.
        fn = tool.get("function") if isinstance(tool.get("function"), dict) else tool
        entry = clean_block(
            {
                "name": fn.get("name") if isinstance(fn.get("name"), str) else None,
                "description": fn.get("description")
                if isinstance(fn.get("description"), str)
                else None,
                "schema": fn.get("parameters") or fn.get("schema"),
            }
        )
        if entry:
            out.append(entry)
    return out or None


def assemble(
    source: str,
    *,
    source_agent_id: str | None = None,
    llm: dict[str, Any] | None = None,
    stt: dict[str, Any] | None = None,
    tts: dict[str, Any] | None = None,
    voice: dict[str, Any] | None = None,
    name: str | None = None,
    prompt: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    primary_language: str | None = None,
    phone_number: str | None = None,
    policy_guardrails: str | None = None,
    additional_details: str | None = None,
) -> Manifest:
    """Build a Manifest dict from normalized pieces (omitting empty parts)."""
    manifest: dict[str, Any] = {"source": source}
    if source_agent_id:
        manifest["source_agent_id"] = source_agent_id
    for key, block in (("llm", llm), ("stt", stt), ("tts", tts), ("voice", voice)):
        if block:
            manifest[key] = block

    config: dict[str, Any] = {}
    if name:
        config["identity"] = {"name": name}
    if prompt and prompt.strip():
        config["behavior"] = {"prompt": prompt}
    if tools:
        config["tools"] = tools
    if primary_language:
        config["language"] = {"primary_language": primary_language}
    if phone_number:
        config["telephony"] = {"phone_number": phone_number}
    if policy_guardrails is not None:
        config["policy_guardrails"] = policy_guardrails
    if additional_details is not None:
        config["additional_details"] = additional_details
    if config:
        manifest["config"] = config

    return Manifest(manifest)
