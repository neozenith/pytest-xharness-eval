"""Per-cell fixture workspace materialisation (ADR 0004).

A plain copy of the fixture tree into a work directory under the pytest rootdir.
No git context: skills that need git history are out of scope this iteration.
"""

from __future__ import annotations

# Standard Library
import hashlib
import shutil
from pathlib import PurePath
from typing import TYPE_CHECKING

# Our Libraries
from pytest_xharness_eval.model import registry

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Sequence
    from pathlib import Path


def materialise(fixture: Path, cell_id: str, workdir: Path, overlays: Sequence[Path] = ()) -> Path:
    """Copy ``fixture`` to a pristine per-cell workspace under ``workdir``, then each overlay over it.

    An existing workspace for the same cell is removed first, so every run starts
    from the committed fixture and never from a previous agent's leftovers. An overlay is a
    treatment's directory (ADR 0055): its files are copied in order on top of the fixture,
    and a file at a path the fixture already has replaces it.
    """
    if not fixture.is_dir():
        raise FileNotFoundError(f"fixture directory does not exist: {fixture}")
    slug = "".join(c if c.isalnum() or c in "-_." else "_" for c in cell_id)
    ws = workdir / slug
    if ws.exists():
        shutil.rmtree(ws)
    ws.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(fixture, ws)
    for overlay in overlays:
        shutil.copytree(overlay, ws, dirs_exist_ok=True)
    return ws


def discard(workspace: Path) -> None:
    """Remove a finished cell's workspace and the run directories its harness made beside it (ADR 0062).

    A workspace is scratch once its cell is captured and graded: the evidence is under
    ``results/``. Left in place, a sweep accumulates every agent's downloads (a skill's render
    step alone fetched 675MB per cell) until the disk fills mid-sweep. Each harness keeps its
    own run directory as ``<workspace>.<harness>`` (the claude plugin wrapper, codex's private
    home with its copied credentials); only those exact names are removed, never a pattern,
    because ``<workspace>.*`` would also match a neighbouring cell's workspace
    (``…-gpt-5`` against ``…-gpt-5.6-sol``).
    """
    for path in (workspace, *(workspace.parent / f"{workspace.name}.{name}" for name in registry.names())):
        if path.is_dir():
            shutil.rmtree(path)


def snapshot(root: Path) -> dict[str, str]:
    """Map every file under ``root`` to a content hash, so a run's writes can be diffed."""
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(root))
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


#: Directories a version digest never reads: caches and vendored trees change without the
#: subject changing.
_UNVERSIONED = frozenset({"__pycache__", "node_modules", ".git", ".venv", ".pytest_cache", ".ruff_cache"})


def version(root: Path, paths: Sequence[str], *, exclude: Sequence[str] = ()) -> str:
    """The digest of every file under ``paths`` (relative to ``root``): the subject's version (ADR 0074).

    ``exclude`` names further directory names to skip -- a skill's own ``evals/`` grade the
    skill and are not part of it. A missing path raises: a case that tracks a file that is not
    there would record one version for every edit of the subject.
    """
    skipped = _UNVERSIONED | set(exclude)
    h = hashlib.sha256()
    for rel in sorted(paths):
        # ``rel`` may also be absolute, or climb out of the root: a scenario's tool often lives
        # in its own repository. Files are named relative to the tracked path, never to the
        # root, so the digest does not change when the project is checked out elsewhere.
        target = root / rel
        if not target.exists():
            raise FileNotFoundError(f"tracked path does not exist: {target}")
        # An absolute track is named by its basename: the digest must not move with the checkout.
        name = target.name if PurePath(rel).is_absolute() else rel
        if target.is_file():
            h.update(name.encode("utf-8") + b"\0" + target.read_bytes() + b"\0")
            continue
        for p in sorted(p for p in target.rglob("*") if p.is_file()):
            inner = p.relative_to(target)
            if skipped.intersection(inner.parts):
                continue
            h.update(f"{name}/{inner.as_posix()}".encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()[:12]


def diff(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Paths created or modified between two snapshots."""
    return sorted(k for k, v in after.items() if before.get(k) != v)
