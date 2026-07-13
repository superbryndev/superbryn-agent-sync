# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-07-13

### Added
- Framework adapters now unwrap wrapped pipeline components before extraction:
  - **LiveKit**: `FallbackAdapter` / `StreamAdapter` / custom wrapper classes are descended (cycle-safe) to the base `livekit.plugins.<provider>` instance, so provider/model/voice blocks are no longer silently dropped for wrapped agents. `FallbackAdapter`'s first non-primary instance is reported in the manifest's `fallback` sub-block (`llm`/`stt`/`tts`/`voice`). ElevenLabs-style `_opts.voice_id` added to the voice candidate paths.
  - **Pipecat**: the pipeline walk recurses through nested `Pipeline` / `ParallelPipeline` / `ServiceSwitcher` / `LLMSwitcher` structures (previously one level deep, so switcher members were invisible) and custom wrapper classes are unwrapped. Switcher members produce primary + `fallback` blocks.
- `AmbiguousScanError` (also exported from `superbryn.codescan`): raised when a source scan finds several distinct qualifying prompt candidates instead of silently uploading the longest string found anywhere in a project. Pass `on_ambiguity="longest"` to `build_manifest_from_source` / `fill_manifest_gaps` to opt back into longest-wins.

### Fixed
- `MIN_PROMPT_LENGTH` filtering in codescan was a no-op (`return best if len(best) >= MIN_PROMPT_LENGTH else best`); short placeholder strings like `prompt="hi"` could become `behavior.prompt`. Qualifying candidates now genuinely require 40+ characters.
- Documentation incorrectly claimed adapters read "public attributes only". Extraction reads a fixed allow-list of configuration attributes that includes private fields (`_opts`, `_settings`, `_model`, ...); credential attributes are never in that list. Docs now say so explicitly.

### Changed
- **Codescan never follows symlinks** (neither directories nor files); a scan can no longer escape the given root via a symlink, on any supported Python version.
- Publishing is no longer commit-message driven. The publish workflow publishes exactly the version declared in `pyproject.toml` (skipping if already on PyPI) and refuses to publish without a matching `CHANGELOG.md` section.

## [0.1.4] - 2026-07-11

Last auto-bumped release (commit-message-driven publish workflow). Core SDK:
`Superbryn` / `AsyncSuperbryn` clients, `Manifest` + builder, RFC 8785 (JCS)
content hashing, typed API errors, provider translators (VAPI, Retell,
ElevenLabs, Bland, Bolna, generic), Pipecat/LiveKit adapters, and codescan.

[Unreleased]: https://github.com/superbryndev/superbryn-python-sdk/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/superbryndev/superbryn-python-sdk/compare/v0.1.4...v0.2.0
[0.1.4]: https://github.com/superbryndev/superbryn-python-sdk/releases/tag/v0.1.4
