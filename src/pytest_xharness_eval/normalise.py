"""The shared vocabulary every session log is normalised *into* (ADR 0019, ADR 0021).

Each harness folds its own dialect -- see ``harness/claude.py`` and ``harness/codex.py``
-- but every one of them builds the same ledger with the primitives here: one
:class:`Call` per model API call, carrying the tool calls it issued, the tool results
that entered its context, its text and thinking, and the log line numbers it was built
from. Nothing is truncated: the ledger is the evidence, and the report renders all of it.

A run's ``usage`` is the ledger's sum plus every subagent's, and ``turns`` is the primary
ledger's length; each CLI's own aggregates are kept on ``reported_usage`` /
``reported_turns`` for reconciliation rather than being trusted. Those two derivations are
not here: they belong to :meth:`RunResult.folded` and :meth:`Subagent.folded`, which are
the only places a usage total is summed (ADR 0035).

What is here is the dialect-free machinery every fold needs: reading a numbered JSONL,
flattening a content value, summarising a tool argument, and measuring the gap between two
timestamps. This module knows nothing about any provider. That is the point: a new harness
reuses it without editing it.
"""

from __future__ import annotations

# Standard Library
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path

SUMMARY_CHARS = 120

Numbered = list[tuple[int, dict[str, Any]]]


def read_jsonl_numbered(path: Path) -> Numbered:
    """Parse a JSONL file into ``(line_number, record)`` pairs, skipping blank and unparseable lines.

    Line numbers are 1-based positions in the file, so a ledger can point back at
    the exact evidence it was built from.
    """
    out: Numbered = []
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            out.append((n, json.loads(line)))
        except json.JSONDecodeError:
            continue
    return out


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Parse a JSONL file, skipping blank and unparseable lines."""
    return [rec for _, rec in read_jsonl_numbered(path)]


def text_of(content: Any) -> str:
    """Flatten a content value (string, list of blocks, or other JSON) to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("output") or ""))
            else:
                parts.append(str(block))
        return "\n".join(p for p in parts if p)
    return json.dumps(content) if content is not None else ""


def summarise(name: str, arguments: Any) -> str:
    """A one-line description of a tool call: its most telling argument, truncated for tables only."""
    if isinstance(arguments, str):
        text = arguments
    elif isinstance(arguments, dict):
        for key in ("file_path", "command", "skill", "cmd", "path", "pattern"):
            if key in arguments:
                text = str(arguments[key])
                break
        else:
            text = json.dumps(arguments)
    else:
        text = json.dumps(arguments)
    first = text.strip().split("\n", 1)[0]
    return first[:SUMMARY_CHARS]


def join_text(existing: str, more: str) -> str:
    return (existing + "\n" + more).strip() if more else existing


def ms_between(earlier: str | None, later: str | None) -> int | None:
    """Milliseconds between two ISO-8601 timestamps (``Z`` accepted); None if either is missing or unparseable."""
    if not earlier or not later:
        return None
    try:
        a = datetime.fromisoformat(earlier.replace("Z", "+00:00"))
        b = datetime.fromisoformat(later.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(int((b - a).total_seconds() * 1000), 0)
