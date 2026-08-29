"""Reading back a document this package itself wrote, tolerantly.

A ``result.json`` and a ``history.json`` are read long after they were written -- by the
combine step, by a replay, sometimes by a newer version of this package than the one that
wrote them. Every one of those readers wants the same answer to the same question, so the
question is asked once here: give me the object, or nothing.

Deliberately separate from the harness folding toolkit, which reads a *session log* -- a
foreign document in a provider's dialect, arriving as JSONL. These are our own documents,
they are JSON objects, and an unreadable one is skipped rather than failing a rebuild.
"""

from __future__ import annotations

# Standard Library
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path


def read_json_object(path: Path) -> dict[str, Any] | None:
    """A JSON object read from ``path``, or None when it is absent, malformed or not an object."""
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None
