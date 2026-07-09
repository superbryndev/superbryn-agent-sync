"""LiveKit adapter — build an AgentSyncManifest from a LiveKit Agent.

Lazy submodule: the base ``superbryn`` package does not depend on
LiveKit. Extraction reads public attributes on ``agent.llm`` /
``agent.stt`` / ``agent.tts`` (works for both ``Agent`` and
``AgentSession``) — API keys held by plugin objects are never read.

>>> from superbryn import Superbryn
>>> from superbryn.livekit import build_manifest_from_agent
>>> manifest = build_manifest_from_agent(
...     agent,
...     identity={"name": "Support Agent", "type": "inbound", "agent_modality": "voice"},
...     policy_guardrails=open("guardrails.md").read(),
... )
>>> Superbryn(api_key="sk_agent_...").sync(manifest)
"""

from __future__ import annotations

import logging
from typing import Any

from ..manifest import Manifest

logger = logging.getLogger("superbryn.livekit")

_MODEL_ATTRS = ("model", "_model", "model_name", "_opts.model", "opts.model")
_VOICE_ATTRS = ("voice", "_voice", "voice_id", "_voice_id", "_opts.voice", "opts.voice")
_LANGUAGE_ATTRS = ("language", "_language", "_opts.language", "opts.language")


def _read_attr_chain(source: Any, *names: str) -> Any:
    for name in names:
        cur: Any = source
        for part in name.split("."):
            cur = getattr(cur, part, None)
            if cur is None:
                break
        if cur not in (None, ""):
            return cur
    return None


def _provider_from_plugin(obj: Any) -> str | None:
    """Extract the provider from a livekit.plugins.<provider>.* module path."""
    module = type(obj).__module__ or ""
    parts = module.split(".")
    if "plugins" in parts:
        idx = parts.index("plugins")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return None


def _extract_component(obj: Any, role: str) -> dict[str, Any] | None:
    if obj is None:
        return None
    block: dict[str, Any] = {}

    provider = _provider_from_plugin(obj)
    if provider:
        block["provider"] = provider

    model = _read_attr_chain(obj, *_MODEL_ATTRS)
    if isinstance(model, str) and model:
        block["model"] = model

    if role == "stt":
        language = _read_attr_chain(obj, *_LANGUAGE_ATTRS)
        if isinstance(language, str) and language:
            block["language"] = language

    if role == "tts":
        voice = _read_attr_chain(obj, *_VOICE_ATTRS)
        if isinstance(voice, str) and voice:
            block["voice_id"] = voice

    return block or None


def build_manifest_from_agent(
    agent: Any,
    *,
    source: str = "livekit",
    identity: dict[str, Any] | None = None,
    behavior: dict[str, Any] | None = None,
    tools: list[dict[str, Any]] | None = None,
    language: dict[str, Any] | None = None,
    telephony: dict[str, Any] | None = None,
    policy_guardrails: str | None = None,
    additional_details: str | None = None,
    concurrency_calls: int | None = None,
) -> Manifest:
    """Build an :class:`superbryn.Manifest` from a LiveKit Agent / AgentSession.

    Reads ``agent.llm`` / ``agent.stt`` / ``agent.tts`` for the pipeline
    blocks and ``agent.instructions`` as the behavior prompt unless an
    explicit ``behavior`` override is given. Extraction failures degrade
    to a sparser manifest, never an error.
    """
    manifest: dict[str, Any] = {"source": source}

    try:
        for role in ("llm", "stt", "tts"):
            block = _extract_component(getattr(agent, role, None), role)
            if block:
                manifest[role] = block
    except Exception as exc:  # noqa: BLE001 — never break the customer's agent
        logger.debug("agent extraction failed: %s", exc)

    tts_block = manifest.get("tts")
    if isinstance(tts_block, dict) and tts_block.get("voice_id"):
        manifest["voice"] = {
            k: v
            for k, v in (("provider", tts_block.get("provider")), ("voice_id", tts_block["voice_id"]))
            if v
        }

    if behavior is None:
        instructions = getattr(agent, "instructions", None)
        if isinstance(instructions, str) and instructions.strip():
            behavior = {"prompt": instructions}

    config: dict[str, Any] = {}
    if identity is not None:
        config["identity"] = identity
    if behavior is not None:
        config["behavior"] = behavior
    if tools is not None:
        config["tools"] = tools
    if language is not None:
        config["language"] = language
    if telephony is not None:
        config["telephony"] = telephony
    if policy_guardrails is not None:
        config["policy_guardrails"] = policy_guardrails
    if additional_details is not None:
        config["additional_details"] = additional_details
    if concurrency_calls is not None:
        config["concurrency_calls"] = concurrency_calls
    if config:
        manifest["config"] = config

    return Manifest(manifest)
