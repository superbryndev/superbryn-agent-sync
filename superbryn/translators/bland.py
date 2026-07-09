"""Bland web agent → AgentSyncManifest.

Input is the agent JSON from ``GET https://api.bland.ai/v1/agents/:agent_id``
(or one entry of ``GET /v1/agents``):
- system prompt: ``prompt``
- LLM model:     ``model``
- language:      ``language``
- voice:         ``voice``
- tools:         ``tools[]``
"""

from __future__ import annotations

from typing import Any

from ..manifest import Manifest
from ._util import assemble, clean_block, normalize_tools


def manifest_from_agent(agent: dict[str, Any], *, phone_number: str | None = None) -> Manifest:
    # Some plans wrap the agent as {"agent": {...}}.
    inner = agent.get("agent")
    if isinstance(inner, dict):
        agent = inner

    model = agent.get("model") if isinstance(agent.get("model"), str) else None
    voice = agent.get("voice") if isinstance(agent.get("voice"), str) else None
    language = agent.get("language") if isinstance(agent.get("language"), str) else None
    prompt = agent.get("prompt") if isinstance(agent.get("prompt"), str) else None

    return assemble(
        "bland",
        source_agent_id=agent.get("agent_id") if isinstance(agent.get("agent_id"), str) else None,
        llm=clean_block({"provider": "bland", "model": model}) if model else None,
        voice=clean_block({"provider": "bland", "voice_id": voice}) if voice else None,
        name=agent.get("name") if isinstance(agent.get("name"), str) else None,
        prompt=prompt,
        tools=normalize_tools(agent.get("tools")),
        primary_language=language,
        phone_number=phone_number,
    )
