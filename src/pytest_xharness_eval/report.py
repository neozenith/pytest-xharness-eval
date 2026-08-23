"""``captured/report.html``: a static microsite over the captured JSON (ADR 0020, 0021, 0024).

Every live sweep leaves ``<skill>/evals/captured/`` holding one ``.result.json`` and
one session log per cell, plus ``history.jsonl``. This module writes beside them:

* ``index.json``: one summary row per captured cell, pointing at its result and log
  by relative path, so a page can list the sweep without opening every file.
* ``report.html``: a self-contained page (vanilla JS, pinned CDN libraries) that
  fetches ``index.json`` and drills into each cell's ``.result.json`` ledger.
* ``report.tokens.json``: the design tokens the page is themed with (colours, series,
  category pills, fonts). Edit it and refresh; or point ``design_tokens`` at your own.
* ``XHARNESS-REPORT-GLOSSARY.md``: the names of every element on that page, the
  metrics it shows, and the ids used to address a session or a turn.

The page fetches relative paths, so it is served over HTTP, never opened from
``file://``, unless it is written ``inline``: then the index, every result, every
session log and the tokens are embedded and the single file opens anywhere.
"""

from __future__ import annotations

# Standard Library
import json
from importlib import resources
from typing import TYPE_CHECKING, Any

# Our Libraries
from pytest_xharness_eval import history

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path

INDEX_NAME = "index.json"
PAGE_NAME = "report.html"
TOKENS_NAME = "report.tokens.json"
GLOSSARY_NAME = "XHARNESS-REPORT-GLOSSARY.md"
INLINE_MARKER = "<!--XHARNESS_INLINE_DATA-->"


def _history_by_session(captured: Path) -> dict[str, dict[str, Any]]:
    """The latest ``history.jsonl`` record per session id (a session runs once, but last wins)."""
    path = captured / "history.jsonl"
    if not path.is_file():
        return {}
    out: dict[str, dict[str, Any]] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue
        sid = str(rec.get("session_id") or "")
        if sid:
            out[sid] = rec
    return out


def _row(result_path: Path, result: dict[str, Any], hist: dict[str, Any]) -> dict[str, Any]:
    case = result_path.parent.name
    stem = result_path.name.removesuffix(".result.json")
    log = result_path.with_name(f"{stem}.jsonl")
    usage = result.get("usage") or {}
    tool_calls = result.get("tool_calls") or {}
    meta = result.get("case") or {}
    return {
        "case": case,
        "suite": meta.get("suite"),
        "skill": meta.get("skill"),
        "fixture": meta.get("fixture"),
        "prompt": meta.get("prompt"),
        "harness": result.get("harness"),
        "model": result.get("model"),
        "session_id": result.get("session_id"),
        "verdict": hist.get("verdict"),
        "at": hist.get("at"),
        "node": hist.get("node"),
        "wall_ms": hist.get("wall_ms"),
        "result": f"{case}/{result_path.name}",
        "log": f"{case}/{log.name}" if log.is_file() else None,
        "estimated_cost_usd": result.get("estimated_cost_usd"),
        "harness_reported_cost_usd": result.get("harness_reported_cost_usd"),
        "rates_applied": result.get("rates_applied") or {},
        "accumulative_billed_tokens": usage.get("accumulative_billed_tokens"),
        "baseline_tokens": result.get("baseline_tokens"),
        "context_window": result.get("context_window"),
        "peak_context_tokens": result.get("peak_context_tokens"),
        "context_window_pct": result.get("context_window_pct"),
        "final_context_pct": result.get("final_context_pct"),
        "ttft_ms": result.get("ttft_ms"),
        "output_tokens_per_sec": result.get("output_tokens_per_sec"),
        "turns": result.get("turns"),
        "reported_turns": result.get("reported_turns"),
        "tool_calls": sum(int(v) for v in tool_calls.values()),
        "duration_ms": result.get("duration_ms"),
        "files_written": result.get("files_written") or [],
        "has_ledger": bool(result.get("calls")),
        "record_kinds": result.get("record_kinds") or {},
        "skill_coverage": (result.get("skill_coverage") or {}).get("summary") or {},
    }


def cells(captured: Path) -> list[dict[str, Any]]:
    """One summary row per ``<case>/<harness>-<session>.result.json`` under ``captured``, newest first."""
    by_session = _history_by_session(captured)
    rows = []
    for result_path in sorted(captured.glob("*/*.result.json")):
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        rows.append(_row(result_path, result, by_session.get(str(result.get("session_id") or ""), {})))
    rows.sort(key=lambda r: str(r.get("at") or ""), reverse=True)
    return rows


def load_tokens(path: Path | None = None) -> dict[str, Any]:
    """The design tokens to theme the page with: the user's file when given, else the bundled default.

    A user file must be a JSON object; a missing file is an error, never a silent
    fallback to the default look.
    """
    if path is None:
        raw = resources.files("pytest_xharness_eval").joinpath("assets", TOKENS_NAME).read_text(encoding="utf-8")
    else:
        if not path.is_file():
            raise FileNotFoundError(f"design tokens file not found: {path}")
        raw = path.read_text(encoding="utf-8")
    tokens = json.loads(raw)
    if not isinstance(tokens, dict) or "themes" not in tokens:
        raise ValueError(f"design tokens must be a JSON object with a 'themes' key: {path or TOKENS_NAME}")
    return tokens


def _inline_payload(captured: Path, index: dict[str, Any], tokens: dict[str, Any]) -> str:
    """Everything the page would otherwise fetch, as one ``<script>`` that sets ``window.__XH_DATA__``."""
    results: dict[str, Any] = {}
    logs: dict[str, str] = {}
    for cell in index["cells"]:
        sid = str(cell["session_id"])
        results[sid] = json.loads((captured / cell["result"]).read_text(encoding="utf-8"))
        if cell.get("log"):
            logs[sid] = (captured / cell["log"]).read_text(encoding="utf-8")
    payload = json.dumps({"index": index, "results": results, "logs": logs, "tokens": tokens})
    # A "</script>" inside a log would end the tag early; "<\/" is the same string to JSON.
    return f"<script>window.__XH_DATA__ = {payload.replace('</', '<\\/')};</script>"


def inline_page(template: str, captured: Path, index: dict[str, Any], tokens: dict[str, Any], inline: bool) -> str:
    """The page text: ``template`` with its inline marker replaced by the payload, or by nothing.

    Public so a build of the page (``report-ui/``) can be exercised against a captured
    directory exactly as ``write`` would ship it.
    """
    if INLINE_MARKER not in template:
        raise RuntimeError(f"report template has no {INLINE_MARKER} marker")
    return template.replace(INLINE_MARKER, _inline_payload(captured, index, tokens) if inline else "")


def write(captured: Path, design_tokens: Path | None = None, inline: bool = False) -> Path:
    """Write ``index.json``, ``report.tokens.json``, ``report.html`` and the glossary into ``captured``.

    ``design_tokens`` themes the page (copied beside it as ``report.tokens.json`` so it can
    still be edited in place). ``inline`` embeds the index, every result and log, and the
    tokens into ``report.html`` so the one file opens over ``file://``.
    """
    captured.mkdir(parents=True, exist_ok=True)
    index = {"generated_at": history.now_iso(), "captured": str(captured), "inline": inline, "cells": cells(captured)}
    (captured / INDEX_NAME).write_text(json.dumps(index, indent=1, sort_keys=True), encoding="utf-8")
    tokens = load_tokens(design_tokens)
    (captured / TOKENS_NAME).write_text(json.dumps(tokens, indent=1), encoding="utf-8")
    assets = resources.files("pytest_xharness_eval").joinpath("assets")
    (captured / GLOSSARY_NAME).write_text(assets.joinpath(GLOSSARY_NAME).read_text(encoding="utf-8"), encoding="utf-8")
    page = inline_page(assets.joinpath(PAGE_NAME).read_text(encoding="utf-8"), captured, index, tokens, inline)
    out = captured / PAGE_NAME
    out.write_text(page, encoding="utf-8")
    return out


def serve_hint(captured: Path) -> str:
    """The one-line command that serves the page (fetch needs HTTP, not ``file://``)."""
    return f"python3 -m http.server 8765 --directory {captured}   # then open http://localhost:8765/{PAGE_NAME}"
