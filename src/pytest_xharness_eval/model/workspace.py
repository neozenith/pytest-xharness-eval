"""Per-cell fixture workspace materialisation (ADR 0004).

A plain copy of the fixture tree into a work directory under the pytest rootdir.
No git context: skills that need git history are out of scope this iteration.
"""

from __future__ import annotations

# Standard Library
import hashlib
import shutil
from typing import TYPE_CHECKING

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


def snapshot(root: Path) -> dict[str, str]:
    """Map every file under ``root`` to a content hash, so a run's writes can be diffed."""
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(root))
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def diff(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Paths created or modified between two snapshots."""
    return sorted(k for k, v in after.items() if before.get(k) != v)
