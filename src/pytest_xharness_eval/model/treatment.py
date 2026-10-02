"""Treatments: the opt-in fourth matrix axis, layered over a case's fixture (ADR 0055).

A *treatment* is a named directory of files copied over the fixture after the fixture is
copied -- an ``AGENTS.md``, a ``CLAUDE.md``, a hook's settings -- so one case can be swept
with and without a change to the agent's instructions while everything else is held
still. The cell with no treatment is the *control*: it is always swept beside the
treatments, because a treatment measured without its control is a number with nothing to
be compared to.

A treatment lives beside the fixtures it is layered over, in two dialects:

    evals/treatments/<name>/            every harness gets these files
    evals/treatments/<name>__<harness>/ that harness also gets these, copied last

Instruction files are the reason for the second form: codex reads ``AGENTS.md`` and
claude reads ``CLAUDE.md``, so a portable treatment ships an ``AGENTS.md`` and a one-line
``CLAUDE.md`` importing it under ``<name>__claude/``. Nothing here knows either filename;
which file a harness reads is the harness's business (ADR 0034).

Every name a case asks for is checked at collection, before anything is spent: a
treatment that would copy nothing onto some harness's workspace is that harness's control
billed twice under a second name, which is the failure ADR 0049's lens names -- a knob
that every consumer accepts and silently ignores.
"""

from __future__ import annotations

# Standard Library
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterable
    from pathlib import Path

#: The word that names the cell with no treatment, on the command line and on the page.
#: Reserved: a treatment directory may not take it, or ``--treatment control`` would mean
#: two things.
CONTROL = "control"

#: ``evals/treatments/``: where a suite's treatments live, beside ``evals/fixtures/``.
TREATMENTS_DIR = "treatments"

#: What joins a treatment's name to the harness its dialect directory is for.
DIALECT_SEP = "__"

#: What joins a cell to its treatment in a cell id (``claude/claude-sonnet-5+lean-ci``) and
#: in the evidence tree's model level (``claude-sonnet-5--high+lean-ci``). ``+`` because no
#: model id, effort rung or treatment name contains it, and it is literal in a URL path.
TREATMENT_SEP = "+"

# Lowercase words joined by a single ``_`` or ``-``, so a treatment reads like the fixture
# beside it (``unstyled_diagram``). The name appears in a node id, a directory level and a
# URL, so it carries no separator any of them already uses (``/``, ``--``, ``__``, ``+``)
# and no character a filesystem or a URL would rewrite.
_NAME = re.compile(r"^[a-z0-9]+([_-][a-z0-9]+)*$")


class UnknownTreatment(ValueError):
    """A treatment a case asks for cannot be applied as named. Raised at collection."""


def check_name(name: str) -> str:
    """``name`` if it may name a treatment; :exc:`UnknownTreatment` saying why it may not."""
    if name == CONTROL:
        raise UnknownTreatment(
            f"treatment {name!r} is reserved: it names the untreated cell, which every sweep with treatments includes"
        )
    if not _NAME.match(name):
        raise UnknownTreatment(f"treatment {name!r} must be lowercase words joined by a single '_' or '-'")
    return name


def layers(evals_dir: Path, name: str, harness: str) -> list[Path]:
    """The directories copied over the fixture for ``name`` on ``harness``, in copy order.

    The universal directory first, so a dialect file of the same path wins. Either may be
    absent; :func:`validate` is what refuses a treatment that leaves a harness with none.
    """
    root = evals_dir / TREATMENTS_DIR
    candidates = (root / name, root / f"{name}{DIALECT_SEP}{harness}")
    return [d for d in candidates if d.is_dir()]


def validate(evals_dir: Path, names: Iterable[str], harnesses: Iterable[str]) -> None:
    """Refuse, before spend, any treatment that is malformed or copies nothing on a harness.

    ``harnesses`` is every harness the case is about to sweep: a treatment that only has a
    ``__claude`` dialect directory would leave a codex cell identical to its control.
    """
    wanted = sorted(set(harnesses))
    for name in names:
        check_name(name)
        bare = [h for h in wanted if not layers(evals_dir, name, h)]
        if bare:
            where = evals_dir / TREATMENTS_DIR
            raise UnknownTreatment(
                f"treatment {name!r} has no files for {', '.join(bare)}: expected {where / name}/ "
                f"or {where / name}{DIALECT_SEP}<harness>/"
            )
