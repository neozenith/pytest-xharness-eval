"""Running several checkers and reporting every failure, not just the first (ADR 0045).

A grader that calls its checks one after another stops at the first ``AssertionError``,
so a run that broke three things reads as if it broke one, and the next sweep surprises
you with the second. :func:`check_all` runs every one and raises a single
``AssertionError`` that lists each failure under the checker that raised it.

Only failures are gathered. Any other exception -- the ``Unmeasurable`` a tool that
could not run raises, a bug in a checker -- propagates at once and unchanged, because it
means the cell could not be graded (an ``error``), and folding it into a list of fails
would grade it ``fail`` instead.
"""

from __future__ import annotations

# Standard Library
from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Our Libraries
    from pytest_xharness_eval.model.output import CaseOutput

#: One checker bound to its arguments. The output is passed first, so bind keywords with
#: :func:`functools.partial` (``partial(check_cost_within, usd=0.5)``) and positional
#: arguments with a lambda (``lambda o: check_files_written(o, "OUT.md")``). A lambda has no
#: readable name, so give it one as a ``(label, checker)`` pair when the label matters.
Checker = Callable[["CaseOutput"], None]
Labelled = Checker | tuple[str, Checker]


def checker_name(checker: Labelled) -> str | None:
    """A readable name for ``checker``, or None for an unlabelled lambda.

    A ``(label, checker)`` pair is its label; a partial is its function with the bound
    arguments; a function is its qualified name. A lambda's qualified name
    (``_grade.<locals>.<lambda>``) says nothing a reader can use, so it is no name at all.
    """
    if isinstance(checker, tuple):
        return checker[0]
    if isinstance(checker, partial):
        args = [repr(a) for a in checker.args] + [f"{k}={v!r}" for k, v in checker.keywords.items()]
        inner = checker_name(checker.func)
        return f"{inner}({', '.join(args)})" if inner else None
    name = getattr(checker, "__qualname__", None) or repr(checker)
    return None if "<lambda>" in name else name


def check_all(output: CaseOutput, *checkers: Labelled) -> None:
    """Run every checker on ``output``; raise one ``AssertionError`` naming each that failed.

    The message's first line is the first failure's own first line, with ``(+N more)`` when
    others failed too: a cell record keeps only that line (``plugin/cell.py``), so it must
    say *what* failed for failures to group by cause rather than by how many checks broke.
    The full numbered list follows beneath it. A failure is prefixed ``[<name>]`` only when
    its checker has a readable name (:func:`checker_name`).
    """
    failures: list[tuple[str | None, str]] = []
    for checker in checkers:
        run = checker[1] if isinstance(checker, tuple) else checker
        try:
            run(output)
        except AssertionError as exc:
            failures.append((checker_name(checker), str(exc)))
    if failures:
        name, text = failures[0]
        first = next((line.strip() for line in text.splitlines() if line.strip()), "")
        more = f" (+{len(failures) - 1} more)" if len(failures) > 1 else ""
        joined = "\n".join(f"{n}. {_tag(who)}{why}" for n, (who, why) in enumerate(failures, 1))
        raise AssertionError(f"{_tag(name)}{first}{more}\n{len(failures)} of {len(checkers)} checks failed:\n{joined}")


def _tag(name: str | None) -> str:
    return f"[{name}] " if name else ""
