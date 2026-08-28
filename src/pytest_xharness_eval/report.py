"""``<cache>/report/``: one aggregated microsite over everything under ``results/`` (ADR 0020, 0021, 0024, 0032).

Every live cell leaves ``<cache>/results/{skill}/{harness}/{model}/{run}/{session}/``
holding ``log.jsonl``, ``result.json`` and ``history.json``. This module is the one
combine step: it walks the whole tree - every skill, every run - and writes into
``<cache>/report/``:

* ``index.json``: one summary row per captured session, pointing at its result and
  log by relative path (``../results/...``), so a page can list the sweep without
  opening every file.
* ``history.jsonl``: every per-session ``history.json`` record, aggregated and
  sorted by ``at``.
* ``report.html``: the self-contained page that fetches ``index.json`` and drills
  into each session's ledger.
* ``report.tokens.json``: the design tokens the page is themed with (colours, series,
  category pills, fonts). Edit it and refresh; or point ``design_tokens`` at your own.
* ``XHARNESS-REPORT-GLOSSARY.md``: the names of every element on that page, the
  metrics it shows, and the ids used to address a session or a turn.

The page fetches relative paths, so the *cache root* is served over HTTP and the
page opened at ``/report/report.html`` - unless it is written ``inline``: then the
index, every result, every session log and the tokens are embedded and the single
file opens anywhere.
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
HISTORY_NAME = "history.jsonl"
RESULTS_DIR = "results"
REPORT_DIR = "report"
INLINE_MARKER = "<!--XHARNESS_INLINE_DATA-->"


def _history_of(session_dir: Path) -> dict[str, Any]:
    """The session's own metrics record (the suffix file, ADR 0032), or an empty mapping."""
    path = session_dir / "history.json"
    if not path.is_file():
        return {}
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return rec if isinstance(rec, dict) else {}


def _row(cache: Path, result_path: Path, result: dict[str, Any], hist: dict[str, Any]) -> dict[str, Any]:
    session_dir = result_path.parent
    rel = session_dir.relative_to(cache / RESULTS_DIR)  # {skill}/{harness}/{model}/{run}/{session}
    log = session_dir / "log.jsonl"
    usage = result.get("usage") or {}
    tool_calls = result.get("tool_calls") or {}
    meta = result.get("case") or {}
    return {
        "case": meta.get("name") or hist.get("case") or "(unknown case)",
        "run": rel.parts[3] if len(rel.parts) >= 4 else None,
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
        # relative to report/, where index.json and the page live (ADR 0032)
        "result": f"../{RESULTS_DIR}/{rel.as_posix()}/{result_path.name}",
        "log": f"../{RESULTS_DIR}/{rel.as_posix()}/{log.name}" if log.is_file() else None,
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
        "subagents": len(result.get("subagents") or []),
        "tool_calls": sum(int(v) for v in tool_calls.values()),
        "duration_ms": result.get("duration_ms"),
        "files_written": result.get("files_written") or [],
        "has_ledger": bool(result.get("calls")),
        "record_kinds": result.get("record_kinds") or {},
        "skill_coverage": (result.get("skill_coverage") or {}).get("summary") or {},
    }


def cells(cache: Path) -> list[dict[str, Any]]:
    """One summary row per ``results/{skill}/{harness}/{model}/{run}/{session}/result.json``, newest first."""
    rows = []
    for result_path in sorted((cache / RESULTS_DIR).glob("*/*/*/*/*/result.json")):
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        rows.append(_row(cache, result_path, result, _history_of(result_path.parent)))
    rows.sort(key=lambda r: str(r.get("at") or ""), reverse=True)
    return rows


def aggregate_history(cache: Path) -> list[dict[str, Any]]:
    """Every per-session ``history.json`` record under ``results/``, sorted by ``at`` (the combine step)."""
    records = []
    for path in sorted((cache / RESULTS_DIR).glob("*/*/*/*/*/history.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            records.append(rec)
    records.sort(key=lambda r: str(r.get("at") or ""))
    return records


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


def _inline_payload(report_dir: Path, index: dict[str, Any], tokens: dict[str, Any]) -> str:
    """Everything the page would otherwise fetch, as one ``<script>`` that sets ``window.__XH_DATA__``."""
    results: dict[str, Any] = {}
    logs: dict[str, str] = {}
    for cell in index["cells"]:
        sid = str(cell["session_id"])
        results[sid] = json.loads((report_dir / cell["result"]).resolve().read_text(encoding="utf-8"))
        if cell.get("log"):
            logs[sid] = (report_dir / cell["log"]).resolve().read_text(encoding="utf-8")
    payload = json.dumps({"index": index, "results": results, "logs": logs, "tokens": tokens})
    # A "</script>" inside a log would end the tag early; "<\/" is the same string to JSON.
    return f"<script>window.__XH_DATA__ = {payload.replace('</', '<\\/')};</script>"


def inline_page(template: str, report_dir: Path, index: dict[str, Any], tokens: dict[str, Any], inline: bool) -> str:
    """The page text: ``template`` with its inline marker replaced by the payload, or by nothing.

    ``report_dir`` is the directory the index lives in - the cells' relative paths
    resolve against it. Public so a build of the page (``report-ui/``) can be
    exercised against a cache exactly as ``write`` would ship it.
    """
    if INLINE_MARKER not in template:
        raise RuntimeError(f"report template has no {INLINE_MARKER} marker")
    return template.replace(INLINE_MARKER, _inline_payload(report_dir, index, tokens) if inline else "")


def write(cache: Path, design_tokens: Path | None = None, inline: bool = False) -> Path:
    """The combine step (ADR 0032): aggregate ``results/`` into ``<cache>/report/``.

    Writes ``index.json``, ``history.jsonl``, ``report.tokens.json``, ``report.html``
    and the glossary. ``design_tokens`` themes the page (copied beside it as
    ``report.tokens.json`` so it can still be edited in place). ``inline`` embeds the
    index, every result and log, and the tokens into ``report.html`` so the one file
    opens over ``file://``.
    """
    report_dir = cache / REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    index = {"generated_at": history.now_iso(), "captured": str(cache), "inline": inline, "cells": cells(cache)}
    (report_dir / INDEX_NAME).write_text(json.dumps(index, indent=1, sort_keys=True), encoding="utf-8")
    records = aggregate_history(cache)
    (report_dir / HISTORY_NAME).write_text(
        "".join(json.dumps(rec, sort_keys=True) + "\n" for rec in records), encoding="utf-8"
    )
    tokens = load_tokens(design_tokens)
    (report_dir / TOKENS_NAME).write_text(json.dumps(tokens, indent=1), encoding="utf-8")
    assets = resources.files("pytest_xharness_eval").joinpath("assets")
    (report_dir / GLOSSARY_NAME).write_text(
        assets.joinpath(GLOSSARY_NAME).read_text(encoding="utf-8"), encoding="utf-8"
    )
    page = inline_page(assets.joinpath(PAGE_NAME).read_text(encoding="utf-8"), report_dir, index, tokens, inline)
    out = report_dir / PAGE_NAME
    out.write_text(page, encoding="utf-8")
    return out


def serve_hint(cache: Path) -> str:
    """The one-line command that serves the page (fetch needs HTTP, not ``file://``)."""
    return (
        f"python3 -m http.server 8765 --directory {cache}   # then open http://localhost:8765/{REPORT_DIR}/{PAGE_NAME}"
    )
