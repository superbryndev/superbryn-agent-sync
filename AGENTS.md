# superbryn-python-sdk — Agent Guide

Public PyPI package (`superbryn-agent-sync`, import name `superbryn`) for
syncing voice-agent configuration to SuperBryn: manifest building, content
hashing, framework adapters (Pipecat / LiveKit), provider translators, and
static source scanning. Python >= 3.10.

## Layout

```text
superbryn/
  client.py        # Superbryn / AsyncSuperbryn — POST /public-api/v1/agents/me/sync
  manifest.py      # Manifest + fluent ManifestBuilder (fallback/extra supported)
  canonical.py     # RFC 8785 (JCS) canonicalization + SHA-256 manifest hash
  errors.py        # typed API errors + AmbiguousScanError
  schemas/         # bundled agent_sync_manifest.schema.json
  livekit/         # LiveKit adapter (unwraps FallbackAdapter/StreamAdapter/wrappers)
  pipecat/         # Pipecat adapter (recursive walk, switchers, wrapper unwrap)
  codescan/        # static source extraction (opt-in, constrained — see below)
  translators/     # provider JSON → manifest (vapi, retell, elevenlabs, ...)
tests/             # pytest suite — no network, no real frameworks needed
```

## Non-negotiable invariants

- **No secrets are ever extracted or transmitted.** Adapter extraction reads
  a fixed allow-list of configuration attributes (which includes private
  fields like `_opts` / `_settings`); credential attributes (api_key, token,
  secret) must never be added to any candidate list or codescan key set.
  `tests/` locks this down.
- **Wrapped components must be unwrapped** before reading provider/model
  fields (LiveKit `FallbackAdapter`/`StreamAdapter`, Pipecat switchers,
  custom wrappers); fallbacks are represented in `fallback` sub-blocks.
- **Codescan stays constrained.** It never follows symlinks, prefers a
  specific agent file over a project tree, and raises `AmbiguousScanError`
  on competing prompt candidates rather than guessing. Do not loosen these
  defaults.
- **Extraction failures degrade, never raise** (adapters); the client raises
  typed errors (`errors.py`) so deploy pipelines fail loudly.
- **Hash parity with the server.** `canonical.py` must keep producing the
  exact hash the orchestration service computes; the server test vector in
  `tests/test_canonical.py` guards this.

## Versioning and publishing

- `pyproject.toml` is the version source of truth; `.bumpversion.cfg` keeps
  it, `superbryn/__about__.py`, and the README badge in lockstep
  (`bump2version`). Run `uv lock` after bumping.
- The publish workflow (`.github/workflows/publish.yml`) publishes exactly
  the declared version on merge to `main`, skips if already on PyPI, and
  requires a matching `## [X.Y.Z]` section in `CHANGELOG.md`. Never
  reintroduce commit-message-driven auto-bumps.

## Development

```bash
pip install -e ".[dev,async]"
pytest -q                     # no network or API keys needed
ruff format && ruff check superbryn tests
```

- The manifest schema mirrors the orchestration service's
  `AgentSyncManifest` (strict server-side validation). If the schema changes
  upstream, update `schemas/`, the builder, and the tests together.
- Update `CHANGELOG.md` for any behavior change.
