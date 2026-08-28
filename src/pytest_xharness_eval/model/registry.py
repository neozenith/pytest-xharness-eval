"""What the domain may ask of the harness registry, and the one place below it that asks.

*Harness* is the first matrix axis (ADR 0015) and the registry in
:mod:`pytest_xharness_eval.harness` is its only dispatch (ADR 0034). Two questions about
a harness are asked from underneath that layer, both of them lookups by registered name
and neither of them behaviour: which harnesses exist, so the matrix can reject an entry
naming one that does not, and which tool names a harness runs shell commands with, so
skill coverage can tell a script that was *run* from one that was merely read (ADR 0027).

Those two lookups used to be two separate upward imports -- ``matrix`` named the harness
package, and ``skillcov.annotate`` called ``harness.get(result.harness)`` in the middle of
its ledger walk, which is why annotating coverage needed a registered harness at all
(ADR 0039). They are one declared edge now: this module names the adapter layer, the rest
of the domain and the whole derivation layer name this module, and the ruff layer rule in
``pyproject.toml`` fails the build on a third.
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass
from typing import Self

# Our Libraries
from pytest_xharness_eval import harness


def names() -> tuple[str, ...]:
    """The harnesses this plugin can drive: whatever is registered, never a second list."""
    return harness.names()


@dataclass(frozen=True, slots=True, kw_only=True)
class Shells:
    """How one harness runs a shell command: the vocabulary coverage attribution needs.

    ``tools`` are the tool names that mean "ran a shell command"; ``persistent`` are the
    ones of those whose working directory survives into the next call, so a ``cd`` in one
    call is where the next one starts (ADR 0027). ``persistent`` is a subset of ``tools``
    for every shipped harness, and the default is the empty vocabulary: a harness that
    runs no shell has no command to attribute, which is a coherent answer rather than a
    missing one.
    """

    tools: frozenset[str] = frozenset()
    persistent: frozenset[str] = frozenset()

    @classmethod
    def of(cls, name: str) -> Self:
        """The registered harness ``name``'s own vocabulary; an unknown name raises (ADR 0034)."""
        agent = harness.get(name)
        return cls(tools=agent.shell_tools, persistent=agent.persistent_shells)
