"""Retell agent (+ Retell LLM) → AgentSyncManifest.

Retell splits config across two resources:
- agent:  ``GET https://api.retellai.com/get-agent/:agent_id``
  (voice_id, language, response_engine pointer)
- llm:    ``GET https://api.retellai.com/get-retell-llm/:llm_id``
  (general_prompt, states[].state_prompt, model, general_tools)

Pass both payloads; ``llm`` is optional when the agent uses a
conversation-flow response engine.
"""

from __future__ import annotations

from typing import Any

from ..manifest import Manifest
from ._util import assemble, clean_block, normalize_tools


def _combine_prompt(llm: dict[str, Any]) -> str | None:
    general = llm.get("general_prompt") if isinstance(llm.get("general_prompt"), str) else ""
    states = llm.get("states") if isinstance(llm.get("states"), list) else []
    blocks = []
    for state in states:
        if not isinstance(state, dict):
            continue
        state_prompt = state.get("state_prompt")
        if isinstance(state_prompt, str) and state_prompt.strip():
            blocks.append(f"## State: {state.get('name', 'state')}\n{state_prompt}")
    combined = "\n\n---\n\n".join(part for part in [general, "\n\n".join(blocks)] if part.strip())
    return combined or None


def manifest_from_agent(
    agent: dict[str, Any],
    llm: dict[str, Any] | None = None,
    *,
    phone_number: str | None = None,
) -> Manifest:
    llm = llm if isinstance(llm, dict) else {}

    llm_block = clean_block(
        {
            "provider": "retell",
            "model": llm.get("model") if isinstance(llm.get("model"), str) else None,
            "temperature": llm.get("model_temperature"),
        }
    )
    voice_block = clean_block(
        {
            "provider": "retell",
            "voice_id": agent.get("voice_id") if isinstance(agent.get("voice_id"), str) else None,
        }
    )
    # Retell manages STT internally; only the conversation language is exposed.
    language = agent.get("language") if isinstance(agent.get("language"), str) else None

    return assemble(
        "retell",
        source_agent_id=agent.get("agent_id") if isinstance(agent.get("agent_id"), str) else None,
        llm=llm_block if llm else None,
        voice=voice_block if voice_block and voice_block.get("voice_id") else None,
        name=agent.get("agent_name") if isinstance(agent.get("agent_name"), str) else None,
        prompt=_combine_prompt(llm),
        tools=normalize_tools(llm.get("general_tools")),
        primary_language=language,
        phone_number=phone_number,
    )
