"""Static source scanning internals for :mod:`superbryn.codescan`."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..manifest import SYNC_SOURCES, Manifest

PY_SUFFIXES = {".py"}
JS_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
SKIP_DIRS = {
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
    "site-packages",
    ".next",
    ".turbo",
}

PROMPT_KEYS = {
    "prompt",
    "system_prompt",
    "systemprompt",
    "instructions",
    "system_message",
    "systemmessage",
    "agent_prompt",
    "base_prompt",
    "general_prompt",
}
MODEL_KEYS = {"model", "model_name", "model_id", "llm_model", "modelname", "modelid"}
VOICE_KEYS = {"voice", "voice_id", "voiceid"}
LANGUAGE_KEYS = {"language", "primary_language"}
TEMPERATURE_KEYS = {"temperature"}
MAX_TOKEN_KEYS = {"max_tokens", "maxtokens"}
PHONE_KEYS = {"phone_number", "phonenumber"}

PROVIDER_KEYWORDS = (
    "openai",
    "anthropic",
    "google",
    "gemini",
    "azure",
    "groq",
    "together",
    "deepgram",
    "assemblyai",
    "cartesia",
    "elevenlabs",
    "rime",
    "playht",
    "sarvam",
    "hooman",
    "shunya",
)

ROLE_HINTS = (
    ("stt", ("stt", "transcriber", "asr", "speechtotext")),
    ("tts", ("tts", "synthesizer", "texttospeech")),
    ("llm", ("llm", "chat", "completion", "gpt", "claude", "gemini")),
)

# Minimum length before a prompt-key string is considered a real system
# prompt (filters out placeholders like prompt="hi").
MIN_PROMPT_LENGTH = 40


@dataclass
class Finding:
    """One extracted (key, value) with the context it was found in."""

    file: str
    key: str
    value: Any
    role: str | None = None
    provider: str | None = None


@dataclass
class ScanFindings:
    prompts: list[Finding] = field(default_factory=list)
    models: list[Finding] = field(default_factory=list)
    voices: list[Finding] = field(default_factory=list)
    languages: list[Finding] = field(default_factory=list)
    temperatures: list[Finding] = field(default_factory=list)
    max_tokens: list[Finding] = field(default_factory=list)
    phone_numbers: list[Finding] = field(default_factory=list)
    files_scanned: int = 0


def _classify_call(callable_name: str) -> tuple[str | None, str | None]:
    """(role, provider) hints from a called class/function name."""
    lowered = callable_name.lower()
    provider = next((p for p in PROVIDER_KEYWORDS if p in lowered), None)
    if provider == "gemini":
        provider = "google"
    role = None
    for candidate, needles in ROLE_HINTS:
        if any(needle in lowered for needle in needles):
            role = candidate
            break
    return role, provider


def _bucket_for_key(findings: ScanFindings, key: str) -> list[Finding] | None:
    if key in PROMPT_KEYS:
        return findings.prompts
    if key in MODEL_KEYS:
        return findings.models
    if key in VOICE_KEYS:
        return findings.voices
    if key in LANGUAGE_KEYS:
        return findings.languages
    if key in TEMPERATURE_KEYS:
        return findings.temperatures
    if key in MAX_TOKEN_KEYS:
        return findings.max_tokens
    if key in PHONE_KEYS:
        return findings.phone_numbers
    return None


# ── Python (ast) ─────────────────────────────────────────────────────────────


def _callable_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_callable_name(node.value)}.{node.attr}"
    return ""


class _PyVisitor(ast.NodeVisitor):
    def __init__(self, file: str, findings: ScanFindings):
        self.file = file
        self.findings = findings
        self.assignments: dict[str, Any] = {}

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        # Remember simple constant assignments so `prompt=SYSTEM_PROMPT`
        # style references resolve.
        if isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.assignments[target.id] = node.value.value
        self.generic_visit(node)

    def _resolve(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return self.assignments.get(node.id)
        if isinstance(node, ast.JoinedStr):
            # f-string: keep only the constant parts (best effort).
            parts = [v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str)]
            return "".join(parts) or None
        return None

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        role, provider = _classify_call(_callable_name(node.func))
        for keyword in node.keywords:
            if keyword.arg is None:
                continue
            key = keyword.arg.lower()
            bucket = _bucket_for_key(self.findings, key)
            if bucket is None:
                continue
            value = self._resolve(keyword.value)
            if value is None or value == "":
                continue
            bucket.append(Finding(file=self.file, key=key, value=value, role=role, provider=provider))
        self.generic_visit(node)


def _scan_python(path: Path, findings: ScanFindings) -> None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return
    _PyVisitor(str(path), findings).visit(tree)


# ── JS / TS (regex) ──────────────────────────────────────────────────────────

_ALL_KEYS = PROMPT_KEYS | MODEL_KEYS | VOICE_KEYS | LANGUAGE_KEYS | PHONE_KEYS
_JS_STRING_RE = re.compile(
    r"""["']?(?P<key>[A-Za-z_][A-Za-z0-9_]*)["']?\s*[:=]\s*(?P<quote>["'`])(?P<value>(?:\\.|(?!(?P=quote)).)*)(?P=quote)""",
    re.DOTALL,
)
_JS_NUMBER_RE = re.compile(
    r"""["']?(?P<key>temperature|max_tokens|maxTokens)["']?\s*[:=]\s*(?P<value>\d+(?:\.\d+)?)""",
)


def _normalize_js_key(key: str) -> str:
    # camelCase → snake_case so systemPrompt/voiceId map onto the key sets.
    return re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()


def _scan_js(path: Path, findings: ScanFindings) -> None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    lowered = text.lower()
    provider = next((p for p in PROVIDER_KEYWORDS if p in lowered), None)
    if provider == "gemini":
        provider = "google"

    for match in _JS_STRING_RE.finditer(text):
        key = _normalize_js_key(match.group("key"))
        if key not in _ALL_KEYS:
            continue
        value = match.group("value")
        if "${" in value or not value:
            continue  # interpolated template literal — unresolvable statically
        bucket = _bucket_for_key(findings, key)
        if bucket is not None:
            bucket.append(Finding(file=str(path), key=key, value=value, provider=provider))

    for match in _JS_NUMBER_RE.finditer(text):
        key = _normalize_js_key(match.group("key"))
        bucket = _bucket_for_key(findings, key)
        if bucket is None:
            continue
        raw = match.group("value")
        bucket.append(
            Finding(file=str(path), key=key, value=float(raw) if "." in raw else int(raw), provider=provider)
        )


# ── public surface ───────────────────────────────────────────────────────────


def scan_source(root: str | Path) -> ScanFindings:
    """Scan a file or directory tree and return the raw findings."""
    root_path = Path(root)
    findings = ScanFindings()

    paths: list[Path]
    if root_path.is_file():
        paths = [root_path]
    else:
        paths = [
            p
            for p in sorted(root_path.rglob("*"))
            if p.is_file() and not any(part in SKIP_DIRS for part in p.parts)
        ]

    for path in paths:
        if path.suffix in PY_SUFFIXES:
            _scan_python(path, findings)
            findings.files_scanned += 1
        elif path.suffix in JS_SUFFIXES:
            _scan_js(path, findings)
            findings.files_scanned += 1
    return findings


def _pick_prompt(findings: ScanFindings) -> str | None:
    texts = [f.value for f in findings.prompts if isinstance(f.value, str) and f.value.strip()]
    if not texts:
        return None
    best = max(texts, key=len)
    return best if len(best) >= MIN_PROMPT_LENGTH else best


def _first(findings: list[Finding], role: str | None = None) -> Finding | None:
    """First finding classified as `role`; with role=None, first of any role."""
    for finding in findings:
        if role is None or finding.role == role:
            return finding
    return None


def _first_llm_or_generic(findings: list[Finding]) -> Finding | None:
    """Prefer llm-classified hits, then unclassified ones — never hits that
    were already attributed to the stt/tts pipeline stages."""
    return _first(findings, role="llm") or next((f for f in findings if f.role is None), None)


def build_manifest_from_source(
    root: str | Path,
    *,
    source: str = "custom",
    source_agent_id: str | None = None,
    identity: dict[str, Any] | None = None,
    tools: list[dict[str, Any]] | None = None,
    telephony: dict[str, Any] | None = None,
    policy_guardrails: str | None = None,
    additional_details: str | None = None,
    concurrency_calls: int | None = None,
) -> Manifest:
    """Scan customer source code and assemble an AgentSyncManifest.

    Heuristics: the LONGEST prompt-key string becomes ``behavior.prompt``
    (the real system prompt is almost always the longest string literal in
    an agent codebase); model/temperature/max_tokens hits classified as
    LLM-role fill ``llm``; voice hits fill ``voice``; language hits fill
    ``stt.language`` + ``config.language``. Everything the scan can't see
    is supplied through the keyword overrides.
    """
    if source not in SYNC_SOURCES:
        raise ValueError(f"source must be one of {SYNC_SOURCES}, got {source!r}")

    findings = scan_source(root)
    manifest: dict[str, Any] = {"source": source}
    if source_agent_id:
        manifest["source_agent_id"] = source_agent_id

    llm: dict[str, Any] = {}
    llm_model = _first_llm_or_generic(findings.models)
    if llm_model:
        llm["model"] = str(llm_model.value)
        if llm_model.provider:
            llm["provider"] = llm_model.provider
    temperature = _first_llm_or_generic(findings.temperatures)
    if temperature and isinstance(temperature.value, (int, float)):
        llm["temperature"] = float(temperature.value)
    max_tokens = _first_llm_or_generic(findings.max_tokens)
    if max_tokens and isinstance(max_tokens.value, int):
        llm["max_tokens"] = max_tokens.value
    if llm:
        manifest["llm"] = llm

    stt: dict[str, Any] = {}
    stt_model = _first(findings.models, role="stt")
    if stt_model:
        stt["model"] = str(stt_model.value)
        if stt_model.provider:
            stt["provider"] = stt_model.provider
    language = _first(findings.languages, role="stt") or _first(findings.languages)
    if language and isinstance(language.value, str):
        stt["language"] = language.value
    if stt:
        manifest["stt"] = stt

    tts: dict[str, Any] = {}
    tts_model = _first(findings.models, role="tts")
    if tts_model:
        tts["model"] = str(tts_model.value)
        if tts_model.provider:
            tts["provider"] = tts_model.provider
    voice = _first(findings.voices, role="tts") or _first(findings.voices)
    if voice and isinstance(voice.value, str):
        tts["voice_id"] = voice.value
    if tts:
        manifest["tts"] = tts
    if voice and isinstance(voice.value, str):
        voice_block: dict[str, Any] = {"voice_id": voice.value}
        if voice.provider:
            voice_block["provider"] = voice.provider
        manifest["voice"] = voice_block

    config: dict[str, Any] = {}
    if identity is not None:
        config["identity"] = identity
    prompt = _pick_prompt(findings)
    if prompt:
        config["behavior"] = {"prompt": prompt}
    if tools is not None:
        config["tools"] = tools
    if language and isinstance(language.value, str):
        config["language"] = {"primary_language": language.value}
    phone = _first(findings.phone_numbers)
    if telephony is not None:
        config["telephony"] = telephony
    elif phone and isinstance(phone.value, str):
        config["telephony"] = {"phone_number": phone.value}
    if policy_guardrails is not None:
        config["policy_guardrails"] = policy_guardrails
    if additional_details is not None:
        config["additional_details"] = additional_details
    if concurrency_calls is not None:
        config["concurrency_calls"] = concurrency_calls
    if config:
        manifest["config"] = config

    return Manifest(manifest)


def _deep_fill(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    """Recursively adds keys from `extra` that `base` lacks; base wins on conflict."""
    merged = dict(base)
    for key, value in extra.items():
        if key not in merged:
            merged[key] = value
        elif isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_fill(merged[key], value)
    return merged


def fill_manifest_gaps(manifest: dict[str, Any], root: str | Path) -> Manifest:
    """Tops up a manifest with whatever a source scan can find.

    Public APIs vary wildly in what they return — some providers give back a
    full agent config, others little more than an id. Run this over ANY
    translator's output and the code scan fills only the fields the API
    didn't provide; values already in the manifest always win.

    >>> manifest = translators.vapi.manifest_from_assistant(raw)
    >>> manifest = codescan.fill_manifest_gaps(manifest, "path/to/agent-project")
    """
    scanned = build_manifest_from_source(root, source=manifest.get("source", "custom"))
    return Manifest(_deep_fill(dict(manifest), dict(scanned)))
