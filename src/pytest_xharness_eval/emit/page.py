"""The combine step: everything under ``results/`` assembled into ``<cache>/report/``.

Every live cell leaves ``<cache>/results/{skill}/{harness}/{model}/{run}/{session}/``
holding ``log.jsonl``, ``result.json`` and ``history.json``. :func:`write` walks the whole
tree -- every skill, every run -- and produces the microsite (ADR 0020, ADR 0032):

* ``index.json``: one :class:`~pytest_xharness_eval.emit.index.IndexRow` per captured
  session, pointing at its result and log by relative path (``../results/...``).
* ``history.jsonl``: every per-session ``history.json`` record, sorted by ``at``.
* ``report.html``: the self-contained page that fetches ``index.json`` and drills into
  each session's ledger.
* ``report.tokens.json``: the design tokens the page is themed with. Edit it and refresh.
* ``XHARNESS-REPORT-GLOSSARY.md``: the names of every element on that page.

The page fetches relative paths, so the *cache root* is served over HTTP and the page
opened at ``/report/report.html`` -- unless it is written ``inline``: then the index, every
result, every session log and the tokens are embedded and the single file opens anywhere.
"""

from __future__ import annotations

# Standard Library
import json
from importlib import resources
from typing import TYPE_CHECKING, Any

# Our Libraries
from pytest_xharness_eval.emit.index import aggregate_history, cells
from pytest_xharness_eval.emit.tokens import load_tokens
from pytest_xharness_eval.model.clock import now_iso
from pytest_xharness_eval.model.layout import GLOSSARY_NAME, PAGE_NAME, REPORT_DIR

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.model.layout import CacheLayout

INLINE_MARKER = "<!--XHARNESS_INLINE_DATA-->"


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
