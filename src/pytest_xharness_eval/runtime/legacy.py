"""Migrating a pre-0032 ``<skill>/evals/captured`` directory into a cache root (ADR 0032, ADR 0040).

Before ADR 0032, a run wrote its evidence beside the skill it graded: one
``<case>/<harness>-<session>.result.json`` per session with the session log next to it,
and a single ``history.jsonl`` shared by every session of every run. Pointed at such a
directory, ``python -m pytest_xharness_eval.replay`` copies it into the project's cache
root and rebuilds from there; the original is left exactly as it was.

This is transitional code with a known end: the day the last such directory is gone it is
deleted, and being its own module is what makes that a one-file deletion rather than an
excavation of the replay entry point (ADR 0040).
"""

from __future__ import annotations

# Standard Library
import json
import logging
import re
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Self

# Our Libraries
from pytest_xharness_eval.emit.metrics import CellMetrics
from pytest_xharness_eval.model.documents import read_json_object
from pytest_xharness_eval.model.layout import AGGREGATED_HISTORY_NAME, CacheLayout

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path

log = logging.getLogger(__name__)

# The stamp a run directory is named with when the record it is migrated from has no
# usable timestamp; sorts before every real one rather than raising (ADR 0038).
ZERO_RUN_STAMP = "00000000T000000Z"


def run_stamp_of(value: str) -> str:
    """An ISO ``at`` timestamp as the path-safe run stamp (``20260826T042617Z``)."""
    digits = re.sub(r"[^0-9T]", "", value.split("+")[0].split(".")[0])
    return f"{digits}Z" if re.fullmatch(r"\d{8}T\d{6}", digits) else ZERO_RUN_STAMP


@dataclass(frozen=True, slots=True)
class LegacyCapture:
    """One pre-0032 ``captured/`` directory, and the migration of it into a cache root.

    Built only by :meth:`found_at`, which recognises the layout rather than trusting the
    caller: a migration cannot be started against a directory that is not one of these,
    and the entry point therefore has no "is it legacy?" question left to ask twice.
    """

    path: Path

    @classmethod
    def found_at(cls, path: Path) -> Self | None:
        """The legacy capture directory ``path`` is, or None when it is not one.

        Recognised by shape, not by name alone: a directory called ``captured`` holding at
        least one ``<case>/<harness>-<session>.result.json``.
        """
        return cls(path) if path.name == "captured" and any(path.glob("*/*.result.json")) else None

    @property
    def skill(self) -> str:
        """The skill these captures graded: ``<skill>/evals/captured`` names it two levels up."""
        return self.path.resolve().parent.parent.name

    def records(self) -> dict[str, CellMetrics]:
        """The latest ``history.jsonl`` record per session id, read as the current type.

        A pre-0032 line carries keys this version dropped and lacks ones it added; reading
        it through :meth:`CellMetrics.from_dict` migrates it to today's shape in the same
        step that migrates its location (ADR 0037). An unparsable line is skipped: this is
        a best-effort recovery of metadata that cannot be re-derived, not a validation.
        """
        by_session: dict[str, CellMetrics] = {}
        path = self.path / AGGREGATED_HISTORY_NAME
        if not path.is_file():
            return by_session
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            sid = str(rec.get("session_id") or "")
            if sid:
                by_session[sid] = CellMetrics.from_dict(rec)
        return by_session

    def migrate_into(self, cache: Path) -> int:
        """Copy every session into ``<cache>/results/``; return how many were copied.

        The original directory is untouched, and a session whose destination already holds
        a result is skipped, so the migration is idempotent and can be re-run after a
        partial one.
        """
        layout = CacheLayout(cache)
        by_session = self.records()
        skill = self.skill

        migrated = 0
        for result_path in sorted(self.path.glob("*/*.result.json")):
            result = read_json_object(result_path)
            if result is None:
                continue
            sid = str(result.get("session_id") or "")
            previous = by_session.get(sid)
            session = layout.session(
                skill=skill,
                harness=str(result.get("harness") or "unknown"),
                model=str(result.get("model") or "unknown"),
                run=run_stamp_of(previous.at if previous else ""),
                session=sid,
            )
            if session.result.is_file():
                continue
            session.mkdir()
            session.result.write_text(json.dumps(result, indent=1, sort_keys=True), encoding="utf-8")
            stem = result_path.name.removesuffix(".result.json")
            legacy_log = result_path.with_name(f"{stem}.jsonl")
            if legacy_log.is_file():
                session.log.write_bytes(legacy_log.read_bytes())
            if previous is not None:
                # The record moves into the tree it now belongs to, so it names that tree.
                replace(previous, cache=str(cache)).write(session.history)
            migrated += 1
            log.info("migrated %s -> %s", result_path.relative_to(self.path), session.path.relative_to(cache))
        return migrated
