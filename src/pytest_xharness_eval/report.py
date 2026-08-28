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
from dataclasses import asdict, dataclass, field
from importlib import resources
from typing import TYPE_CHECKING, Any, Self

# Our Libraries
from pytest_xharness_eval.layout import (
    GLOSSARY_NAME,
    INDEX_NAME,
    LOG_NAME,
    PAGE_NAME,
    REPORT_DIR,
    RESULT_NAME,
    TOKENS_NAME,
)
from pytest_xharness_eval.metrics import CellMetrics
from pytest_xharness_eval.normalise import now_iso, read_json_object

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Mapping
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.layout import CacheLayout, SessionDir

INLINE_MARKER = "<!--XHARNESS_INLINE_DATA-->"

# ``report-ui/scripts/inline.py`` builds the page against a cache through this module, so
# the three layout names it needs are part of this module's surface as well.
__all__ = [
    "INDEX_NAME",
    "INLINE_MARKER",
    "REPORT_DIR",
    "TOKENS_NAME",
    "IndexRow",
    "aggregate_history",
    "cells",
    "inline_page",
    "load_tokens",
    "serve_hint",
    "write",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexRow:
    """One row of ``report/index.json``: everything the page lists without opening a file.

    The row is a *view over two stored documents* -- a session's ``result.json`` and its
    ``history.json`` -- which is why the values coming off the result are read defensively:
    the combine step indexes whatever a cache holds, including captures written before a
    field existed. The field names are the row's wire format, mirrored by
    ``report-ui/src/lib/types.ts`` and pinned by ``tests/test_units.py``.
    """

    # Which case, run and cell this was.
    case: str
    run: str
    suite: str | None
    skill: str | None
    fixture: str | None
    prompt: str | None
    harness: str | None
    model: str | None
    session_id: str | None
    # How it graded, from the metrics record; None when the session has none.
    verdict: str | None
    at: str | None
    node: str | None
    wall_ms: int | None
    # Where the evidence is, relative to report/ (ADR 0032).
    result: str
    log: str | None
    # What it cost and spent.
    estimated_cost_usd: float | None
    harness_reported_cost_usd: float | None
    rates_applied: dict[str, Any] = field(default_factory=dict)
    accumulative_billed_tokens: int | None = None
    baseline_tokens: int | None = None
    context_window: int | None = None
    peak_context_tokens: int | None = None
    context_window_pct: float | None = None
    final_context_pct: float | None = None
    ttft_ms: int | None = None
    output_tokens_per_sec: float | None = None
    # What it did.
    turns: int | None = None
    reported_turns: int | None = None
    subagents: int = 0
    tool_calls: int = 0
    duration_ms: int | None = None
    files_written: list[str] = field(default_factory=list)
    has_ledger: bool = False
    record_kinds: dict[str, int] = field(default_factory=dict)
    skill_coverage: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def of(cls, session: SessionDir, result: Mapping[str, Any], hist: CellMetrics | None) -> Self:
        """Summarise one captured session from its result and its metrics record."""
        usage = result.get("usage") or {}
        tool_calls = result.get("tool_calls") or {}
        meta = result.get("case") or {}
        return cls(
            case=meta.get("name") or (hist.case if hist else None) or "(unknown case)",
            run=session.run,
            suite=meta.get("suite"),
            skill=meta.get("skill"),
            fixture=meta.get("fixture"),
            prompt=meta.get("prompt"),
            harness=result.get("harness"),
            model=result.get("model"),
            session_id=result.get("session_id"),
            verdict=hist.verdict if hist else None,
            at=hist.at if hist else None,
            node=hist.node if hist else None,
            wall_ms=hist.wall_ms if hist else None,
            result=session.report_link(RESULT_NAME),
            log=session.report_link(LOG_NAME) if session.log.is_file() else None,
            estimated_cost_usd=result.get("estimated_cost_usd"),
            harness_reported_cost_usd=result.get("harness_reported_cost_usd"),
            rates_applied=result.get("rates_applied") or {},
            accumulative_billed_tokens=usage.get("accumulative_billed_tokens"),
            baseline_tokens=result.get("baseline_tokens"),
            context_window=result.get("context_window"),
            peak_context_tokens=result.get("peak_context_tokens"),
            context_window_pct=result.get("context_window_pct"),
            final_context_pct=result.get("final_context_pct"),
            ttft_ms=result.get("ttft_ms"),
            output_tokens_per_sec=result.get("output_tokens_per_sec"),
            turns=result.get("turns"),
            reported_turns=result.get("reported_turns"),
            subagents=len(result.get("subagents") or []),
            tool_calls=sum(int(v) for v in tool_calls.values()),
            duration_ms=result.get("duration_ms"),
            files_written=result.get("files_written") or [],
            has_ledger=bool(result.get("calls")),
            record_kinds=result.get("record_kinds") or {},
            skill_coverage=(result.get("skill_coverage") or {}).get("summary") or {},
        )

    def to_dict(self) -> dict[str, Any]:
        """The JSON-ready mapping this row is in ``index.json``."""
        return asdict(self)


def cells(cache: CacheLayout) -> list[dict[str, Any]]:
    """One summary row per captured session, newest first; a session with no result is skipped."""
    rows = []
    for session in cache.sessions():
        result = read_json_object(session.result)
        if result is None:
            continue
        rows.append(IndexRow.of(session, result, CellMetrics.stored(session.history)).to_dict())
    rows.sort(key=lambda r: str(r.get("at") or ""), reverse=True)
    return rows


def aggregate_history(cache: CacheLayout) -> list[CellMetrics]:
    """Every session's own metrics record, sorted by ``at`` (the combine step, ADR 0032)."""
    records = [m for session in cache.sessions() if (m := CellMetrics.stored(session.history)) is not None]
    records.sort(key=lambda rec: rec.at)
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


def write(cache: CacheLayout, design_tokens: Path | None = None, inline: bool = False) -> Path:
    """The combine step (ADR 0032): aggregate ``results/`` into ``<cache>/report/``.

    Writes ``index.json``, ``history.jsonl``, ``report.tokens.json``, ``report.html``
    and the glossary. ``design_tokens`` themes the page (copied beside it as
    ``report.tokens.json`` so it can still be edited in place). ``inline`` embeds the
    index, every result and log, and the tokens into ``report.html`` so the one file
    opens over ``file://``.
    """
    report_dir = cache.report
    report_dir.mkdir(parents=True, exist_ok=True)
    index = {"generated_at": now_iso(), "captured": str(cache.root), "inline": inline, "cells": cells(cache)}
    cache.index.write_text(json.dumps(index, indent=1, sort_keys=True), encoding="utf-8")
    cache.history.write_text(
        "".join(json.dumps(rec.to_dict(), sort_keys=True) + "\n" for rec in aggregate_history(cache)), encoding="utf-8"
    )
    tokens = load_tokens(design_tokens)
    cache.tokens.write_text(json.dumps(tokens, indent=1), encoding="utf-8")
    assets = resources.files("pytest_xharness_eval").joinpath("assets")
    cache.glossary.write_text(assets.joinpath(GLOSSARY_NAME).read_text(encoding="utf-8"), encoding="utf-8")
    page = inline_page(assets.joinpath(PAGE_NAME).read_text(encoding="utf-8"), report_dir, index, tokens, inline)
    cache.page.write_text(page, encoding="utf-8")
    return cache.page


def serve_hint(cache: CacheLayout) -> str:
    """The one-line command that serves the page (fetch needs HTTP, not ``file://``)."""
    return (
        f"python3 -m http.server 8765 --directory {cache.root}"
        f"   # then open http://localhost:8765/{REPORT_DIR}/{PAGE_NAME}"
    )
