"""Linking every spawned thread to the record that spawned it, or stopping the fold (ADR 0072).

A subagent is evidence twice over: the spawning thread logs a spawn record, and the spawned
thread writes a transcript of its own. Each dialect reads both sides into the two shapes
here, and :func:`link` pairs them one to one. Anything other than an exact pairing is a
:class:`SubagentMismatch`: a transcript no spawn names, a spawn whose transcript is missing,
or a transcript claiming a parent that did not spawn it. A silent gap there would bill a run
for work it never shows, or show work it was never billed for.

Nothing here knows a dialect. What a spawn record looks like, and what a transcript
answers to, is the harness's to read.
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

# Our Libraries
from pytest_xharness_eval.harness.base import RunError

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterable

    # Our Libraries
    from pytest_xharness_eval.model.runresult import Call

#: The id :class:`Spawn.thread` and :class:`Thread.parent` give the primary thread.
PRIMARY = ""


class SubagentMismatch(RunError):
    """A session's spawn records and its thread transcripts do not pair one to one."""


@dataclass(frozen=True, slots=True)
class Spawn:
    """One spawn record: who logged it, in which of its turns, and what the new thread answers to."""

    #: The spawning thread's id, :data:`PRIMARY` for the session itself.
    thread: str
    #: The spawning thread's turn (``Call.n``) whose record this is.
    turn: int
    #: The record's own id, kept on the subagent as ``spawned_by``.
    id: str
    #: The value the spawned thread's transcript names its spawn by.
    key: str
    #: False for a spawn its tool result reports as failed: no transcript is owed for it, but
    #: one that does name it is still linked.
    required: bool = True


@dataclass(frozen=True, slots=True)
class Thread:
    """One spawned thread's transcript, as its own metadata describes it."""

    id: str
    #: The thread its metadata says spawned it, :data:`PRIMARY` for the session itself.
    parent: str
    #: Every value a spawn record may name this thread by (one per spawn shape the dialect has).
    keys: frozenset[str]


@dataclass(frozen=True, slots=True)
class Link:
    """Where one thread sits in the session's spawn tree."""

    spawn: Spawn
    depth: int
    #: The primary turn the thread descends from (ADR 0056 credits its work there).
    parent_turn: int


def turn_of_line(calls: list[Call], line: int, where: str) -> int:
    """The turn whose records hold log line ``line``; a line no turn holds is a mismatch."""
    for call in calls:
        if line in call.records:
            return call.n
    raise SubagentMismatch(f"spawn record at line {line} of {where} belongs to no turn of its ledger")


def link(spawns: Iterable[Spawn], threads: Iterable[Thread]) -> dict[str, Link]:
    """Pair each thread with the one spawn that names it, and place it in the tree.

    Every spawn must be claimed by exactly one thread and every thread by exactly one spawn,
    logged by the parent the thread names. The result is keyed by thread id.
    """
    owner = _pair(spawns, threads)
    links: dict[str, Link] = {}

    def place(thread_id: str, path: tuple[str, ...]) -> Link:
        if thread_id in links:
            return links[thread_id]
        if thread_id in path:
            raise SubagentMismatch(f"subagents spawn each other in a cycle: {' -> '.join((*path, thread_id))}")
        spawn = owner[thread_id]
        if spawn.thread == PRIMARY:
            placed = Link(spawn=spawn, depth=1, parent_turn=spawn.turn)
        else:
            above = place(spawn.thread, (*path, thread_id))
            placed = Link(spawn=spawn, depth=above.depth + 1, parent_turn=above.parent_turn)
        links[thread_id] = placed
        return placed

    for thread_id in owner:
        place(thread_id, ())
    return links


def _pair(spawns: Iterable[Spawn], threads: Iterable[Thread]) -> dict[str, Spawn]:
    """Each thread's one spawn, keyed by thread id; any other pairing is a mismatch."""
    by_key: dict[str, Spawn] = {}
    for spawn in spawns:
        if spawn.key in by_key:
            raise SubagentMismatch(f"two spawn records name the same thread: {spawn.key!r}")
        by_key[spawn.key] = spawn

    owner: dict[str, Spawn] = {}
    claimed: dict[str, str] = {}
    for thread in threads:
        if thread.id in owner:
            raise SubagentMismatch(f"two subagent transcripts carry the same thread id {thread.id}")
        hits = [by_key[k] for k in sorted(thread.keys) if k in by_key]
        if len(hits) != 1:
            raise SubagentMismatch(f"subagent {thread.id} is named by {len(hits)} spawn records, not exactly one")
        (spawn,) = hits
        if spawn.thread != thread.parent:
            raise SubagentMismatch(
                f"subagent {thread.id} names {thread.parent or 'the primary'} as its parent,"
                f" but its spawn was logged by {spawn.thread or 'the primary'}"
            )
        if spawn.key in claimed:
            raise SubagentMismatch(f"subagents {claimed[spawn.key]} and {thread.id} claim one spawn record {spawn.id}")
        claimed[spawn.key] = thread.id
        owner[thread.id] = spawn

    unclaimed = sorted(s.id for k, s in by_key.items() if k not in claimed and s.required)
    if unclaimed:
        raise SubagentMismatch(f"spawn records with no captured subagent transcript: {', '.join(unclaimed)}")
    return owner


def span(records: Iterable[tuple[int, dict[str, object]]], where: str) -> tuple[str, str]:
    """The earliest and latest ``timestamp`` a transcript records, as it wrote them.

    By time, not file order: Claude Code can write a record stamped before the one above it.
    A transcript with no timestamp, or one that does not parse, is a mismatch.
    """
    stamps: list[tuple[datetime, str]] = []
    for _, rec in records:
        if rec.get("timestamp"):
            raw = str(rec["timestamp"])
            try:
                stamps.append((datetime.fromisoformat(raw.replace("Z", "+00:00")), raw))
            except ValueError as exc:
                raise SubagentMismatch(f"subagent transcript {where} records an unreadable timestamp {raw!r}") from exc
    if not stamps:
        raise SubagentMismatch(f"subagent transcript {where} records no timestamp, so its span is unknown")
    try:
        return min(stamps)[1], max(stamps)[1]
    except TypeError as exc:
        raise SubagentMismatch(f"subagent transcript {where} mixes zoned and unzoned timestamps") from exc
