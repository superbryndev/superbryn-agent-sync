"""RFC 8785 (JSON Canonicalization Scheme) hashing.

Mirrors the server's implementation (orchestration-service
``agent-sync.hasher.ts``) so a client-side hash pre-check always agrees
with the hash the server would compute for the same manifest:

    hash = sha256(RFC-8785(config))

Only the ``config`` block is hashed. The top-level pipeline blocks
(``llm`` / ``stt`` / ``tts`` / ``voice``), envelope provenance
(``source``, ``source_agent_id``) and the server-managed ``__meta`` key
are all excluded — pipeline telemetry alone never changes the hash.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

HASHED_KEYS = ("config",)


def _serialize(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        # ensure_ascii=False matches ECMAScript JSON.stringify (raw UTF-8).
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Cannot canonicalize non-finite number")
        if value == int(value) and abs(value) < 1e21:
            # ECMAScript serializes integral floats without a fraction part.
            return str(int(value))
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_serialize(item) for item in value) + "]"
    if isinstance(value, dict):
        members = []
        for key in sorted(value.keys()):
            if value[key] is _OMIT:
                continue
            members.append(json.dumps(str(key), ensure_ascii=False) + ":" + _serialize(value[key]))
        return "{" + ",".join(members) + "}"
    raise TypeError(f"Cannot canonicalize value of type {type(value).__name__}")


_OMIT = object()


def canonicalize(value: Any) -> str:
    """Serialize ``value`` per RFC 8785 (sorted keys, deterministic scalars)."""
    return _serialize(value)


def extract_sync_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    """The hashable body: the ``config`` block only."""
    return {k: manifest[k] for k in HASHED_KEYS if k in manifest}


def compute_manifest_hash(manifest: dict[str, Any]) -> str:
    """``sha256(RFC-8785(config))`` hex digest."""
    return hashlib.sha256(canonicalize(manifest.get("config", {})).encode("utf-8")).hexdigest()
