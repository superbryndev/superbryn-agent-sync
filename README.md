# SuperBryn Agent Sync

[![PyPI version](https://img.shields.io/badge/pypi-v0.1.4-orange)](https://pypi.org/project/superbryn-agent-sync/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Zero dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](https://pypi.org/project/superbryn-agent-sync/)

Sync your voice-agent configuration to [SuperBryn](https://www.superbryn.com) for review, versioning, and monitoring — from any framework (Pipecat, LiveKit) or provider (Vapi, Retell, ElevenLabs, Bland, Bolna, …), or straight from your source code.

A pushed manifest **never changes your live agent directly**. It lands as a pending draft that you review, diff, and approve in the SuperBryn dashboard. On approval (once verification passes), SuperBryn promotes the draft to a new agent version.

## Features

- **Zero runtime dependencies** — the blocking client uses stdlib `urllib`; add `aiohttp` only if you want the async client.
- **Draft-first sync** — every push lands as a pending draft for human review; nothing goes live without approval.
- **Client-side content hashing** — same RFC 8785 (JCS) + SHA-256 hashing as the server, so you can pre-check and skip no-op pushes.
- **Manifest builder** — fluent, typed builder for identity, behavior, LLM / STT / TTS / voice, tools, language, telephony, guardrails, and concurrency.
- **Framework adapters** — build a manifest directly from a Pipecat pipeline or a LiveKit agent; public attributes only, never API keys.
- **Provider translators** — turn Vapi / Retell / ElevenLabs / Bland / Bolna agent JSON into a manifest, best-effort and never erroring on unknown fields.
- **Source-code extraction** — `codescan` statically scans your agent's code (Python `ast`, conservative JS/TS regexes) to fill prompt, models, voice, and phone number when no API can.
- **Typed errors** — auth, scope, validation, business-rule, and rate-limit failures each raise a distinct exception with details.
- **Bundled JSON Schema** — the canonical manifest schema ships inside the package.

## Prerequisites

- Python **3.10+**
- An **agent-scoped** API key created in the SuperBryn dashboard (**Developers → API Keys**, scope: *Single agent*). Org-wide keys are rejected by the sync endpoints.

## Install

```bash
pip install superbryn-agent-sync            # zero runtime dependencies
pip install "superbryn-agent-sync[async]"   # + aiohttp for the async client
```

The import name is `superbryn`:

```python
from superbryn import Superbryn, Manifest
```

## Quick Start

1. Set your agent-scoped API key in the environment:

   ```bash
   export SUPERBRYN_API_KEY="sk_agent_..."
   ```

2. Build a manifest and sync it:

   ```python
   from superbryn import Superbryn, Manifest

   manifest = (
       Manifest.builder(source="custom")
       .set_identity(name="Support Agent", type="inbound", agent_modality="voice")
       .set_behavior(prompt=open("system_prompt.txt").read())
       .set_llm(provider="openai", model="gpt-4o", temperature=0.7, max_tokens=1024)
       .set_stt(provider="deepgram", model="nova-2", language="en-US")
       .set_tts(provider="cartesia", model="sonic-2")
       .set_voice(provider="cartesia", voice_id="a0e99841-...")
       .add_tool(
           name="lookup_order",
           description="Look up an order by ID",
           schema={"type": "object", "properties": {}},
           server={"type": "http", "url": "https://api.example.com/orders"},
       )
       .set_language(primary_language="en-US", additional_languages=[{"code": "es-US", "priority": 1}])
       .set_telephony(phone_number="+15551234567")
       .set_policy_guardrails(open("guardrails.md").read())
       .set_concurrency_calls(10)
       .build()
   )

   client = Superbryn()  # or Superbryn(api_key="sk_agent_...")
   result = client.sync(manifest)
   # {"agent_row_id": "...", "approval_status": "pending", "verification_status": "...",
   #  "hash": "...", "change_types": [...]}
   ```

3. Open the SuperBryn dashboard, review the pending draft, and approve it to promote a new agent version.

Every manifest field is optional — send only what your integration knows. An empty manifest is valid.

## Client Surface

```python
client.sync(manifest)                  # push; lands as pending draft (or no-op)
```

The async client mirrors the same surface (`pip install "superbryn-agent-sync[async]"`):

```python
from superbryn import AsyncSuperbryn

result = await AsyncSuperbryn(api_key="sk_agent_...").sync(manifest)
```

## Content Hashing

The SDK implements the same RFC 8785 (JCS) + SHA-256 content hashing as the server, so a client-side hash always agrees with the server's:

```python
from superbryn import compute_manifest_hash

local_hash = compute_manifest_hash(manifest)   # == manifest.hash
```

## Framework Adapters

Lazy submodules — the base package depends on neither framework.

### Pipecat

```python
from superbryn import Superbryn
from superbryn.pipecat import build_manifest_from_pipeline

manifest = build_manifest_from_pipeline(
    pipeline,
    identity={"name": "Support Agent", "type": "inbound", "agent_modality": "voice"},
    behavior={"prompt": open("prompt.txt").read()},
    policy_guardrails=open("guardrails.md").read(),
)
Superbryn(api_key="sk_agent_...").sync(manifest)
```

Walks `pipeline._processors` and fills `llm` / `stt` / `tts` / `voice` automatically. Extractors read public attributes only — never API keys.

### LiveKit

```python
from superbryn import Superbryn
from superbryn.livekit import build_manifest_from_agent

manifest = build_manifest_from_agent(
    agent,
    identity={"name": "Support Agent", "type": "inbound", "agent_modality": "voice"},
    policy_guardrails=open("guardrails.md").read(),
)
Superbryn(api_key="sk_agent_...").sync(manifest)
```

Reads `agent.llm` / `agent.stt` / `agent.tts` and uses `agent.instructions` as the behavior prompt.

## Provider Translators

For SaaS platforms the agent config lives in their cloud, not in your process. Fetch the agent JSON from the provider's API, then translate it to a manifest:

```python
import requests
from superbryn import Superbryn
from superbryn.translators import vapi

raw = requests.get(
    "https://api.vapi.ai/assistant/ASSISTANT_ID",
    headers={"Authorization": "Bearer VAPI_KEY"},
).json()

manifest = vapi.manifest_from_assistant(raw)
Superbryn(api_key="sk_agent_...").sync(manifest)
```

| Provider | Translator | Input |
|---|---|---|
| Vapi | `translators.vapi.manifest_from_assistant(raw)` | `GET /assistant/:id` |
| Retell | `translators.retell.manifest_from_agent(agent, llm)` | `GET /get-agent/:id` + `GET /get-retell-llm/:llm_id` |
| ElevenLabs | `translators.elevenlabs.manifest_from_agent(raw)` | `GET /v1/convai/agents/:id` |
| Bland | `translators.bland.manifest_from_agent(raw)` | `GET /v1/agents/:id` |
| Bolna | `translators.bolna.manifest_from_agent(raw)` | `GET /v2/agent/:id` |
| Hooman Labs / Shunya Labs / custom | `translators.generic.manifest_from_prompt(prompt, source=...)` or `codescan.build_manifest_from_source(...)` (see below) | your own prompt + known pipeline facts (no public agent-read API yet) |

All translators are best-effort — unknown or missing fields degrade to a sparser manifest, never an error.

## Source-Code Extraction (works for every provider)

You never know in advance what a provider's public API returns — some give back the full agent config, others little more than an id, and some (Hooman Labs, Shunya Labs, in-house stacks) have no agent-read API at all. Whatever the API does or doesn't return, the customer's own code — the place that instantiates the provider's package/SDK — is always available. `superbryn.codescan` statically scans that code and extracts the prompt, model, voice, language, temperature and phone number.

As the sole source (no API, or the API returned nothing useful):

```python
from superbryn import Superbryn
from superbryn.codescan import build_manifest_from_source

manifest = build_manifest_from_source(
    "path/to/agent-project",          # directory or single file
    source="hooman-labs",
    identity={"name": "Support Agent", "type": "inbound"},  # anything the scan can't see
)
Superbryn(api_key="sk_agent_...").sync(manifest)
```

As a gap filler after ANY translator — the scan adds only the fields the provider's API didn't provide, and API-provided values always win:

```python
from superbryn import codescan, translators

manifest = translators.vapi.manifest_from_assistant(raw)          # may be sparse
manifest = codescan.fill_manifest_gaps(manifest, "path/to/agent-project")
```

How it works:

- Python files are parsed with `ast`: keyword arguments on any call (`prompt=`, `instructions=`, `model=`, `voice_id=`, ...) are collected, and simple variable references (`prompt=SYSTEM_PROMPT`) resolve to their assigned string constants.
- JS/TS files are scanned with conservative regexes for the same keys in object-literal form (`systemPrompt: "..."`, `voiceId: '...'`).
- Called class names classify hits per pipeline stage (`DeepgramSTTService` → stt/deepgram, `CartesiaTTSService` → tts/cartesia), so an STT model never lands in the `llm` block.
- The longest prompt-key string wins as `behavior.prompt`; `node_modules`, virtualenvs and build output are skipped.

Extraction is best-effort and read-only. Run it in CI next to the agent code and every deploy syncs the latest config. Use `scan_source(path)` to inspect the raw findings before building a manifest.

## Manifest Fields

Override sections accept exactly the fields of the canonical manifest schema (unknown keys raise `ValueError` locally — the endpoint rejects them anyway):

| Section | Fields |
|---|---|
| `identity` | `name`, `type` (`inbound`/`outbound`), `agent_modality` (`voice`/`chat`), `description`, `pain_point`, `gender`, `age`, `dob` |
| `behavior` | `prompt`, `flow` |
| `llm` / `stt` / `tts` / `voice` | `provider`, `model` / `voice_id`, plus per-block extras (`temperature`, `max_tokens`, `language`, `fallback`, `extra`) |
| `tools` | list of `{name, description, schema, server: {type, url}}` |
| `language` | `primary_language`, `additional_languages: [{code, priority}]` |
| `telephony` | `phone_number`, `ivr_config` |

Plus top-level strings/ints: `policy_guardrails`, `additional_details`, `concurrency_calls`.

The canonical JSON Schema is bundled with the package:

```python
from superbryn import load_manifest_schema

schema = load_manifest_schema()
```

## Typed Errors

```python
from superbryn import (
    AuthenticationError,     # 401 — bad/revoked key
    ScopeError,              # 403 — key is not agent-scoped
    NotFoundError,           # 404 — resource not found
    ManifestValidationError, # 400 — schema failure (has .details)
    BusinessRuleError,       # 422 — semantic rule failure (has .details)
    RateLimitError,          # 429 — back off and retry
)
```

## Troubleshooting

### Enable debug logs

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("superbryn").setLevel(logging.DEBUG)
```

### Common errors

| Error | Cause | Fix |
|---|---|---|
| `ConfigurationError: no API key` | Missing API key | Pass `api_key=` or set `SUPERBRYN_API_KEY` |
| `AuthenticationError` (401) | Invalid or revoked key | Verify the key in SuperBryn → Developers → API Keys |
| `ScopeError` (403) | Org-wide key used | Create an **agent-scoped** key (scope: *Single agent*) |
| `NotFoundError` (404) | Resource not found | Verify the key belongs to the intended agent |
| `ManifestValidationError` (400) | Manifest fails schema validation | Inspect `.details` for the offending fields |
| `BusinessRuleError` (422) | Semantic rule failure | Inspect `.details` and adjust the manifest |
| `RateLimitError` (429) | Too many requests | Back off and retry |

## Environment Variables

| Variable | Meaning |
|---|---|
| `SUPERBRYN_API_KEY` | Agent-scoped API key (fallback for `api_key=`) |
| `SUPERBRYN_BASE_URL` | API base URL (default `https://api.superbryn.com`) |

## Links

- [Agent Sync documentation](https://docs.superbryn.com/advanced/agent-sync)
- [GitHub repository](https://github.com/superbryndev/superbryn-agent-sync)
- [Issue tracker](https://github.com/superbryndev/superbryn-agent-sync/issues)
- [SuperBryn dashboard](https://try.superbryn.com)

## Support

- Email: support@superbryn.com
- GitHub issues: [Report a bug](https://github.com/superbryndev/superbryn-agent-sync/issues)

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

Made with ❤️ by [SuperBryn](https://www.superbryn.com)
