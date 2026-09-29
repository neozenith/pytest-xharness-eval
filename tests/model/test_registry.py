"""``model.registry``: the one lookup of the harness registry from beneath it (ADR 0039)."""


# Standard Library

# Third Party

# Our Libraries
from pytest_xharness_eval import harness as harnesses
from pytest_xharness_eval.model import matrix as mx


def test_the_registry_is_the_only_list_of_known_harnesses() -> None:
    """The matrix reads the registry, so a harness cannot be runnable but unmatrixable (ADR 0034)."""
    assert mx.known_harnesses() == harnesses.names() == ("claude", "codex")
    assert [harnesses.get(n).name for n in harnesses.names()] == list(harnesses.names())
