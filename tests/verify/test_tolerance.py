"""``verify.tolerance``: each tolerance and the evidence it reports (ADR 0046)."""

from __future__ import annotations

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.verify import (
    Count,
    Exact,
    Jaccard,
    Ratio,
    Superset,
    Within,
)


def test_each_tolerance_reports_its_own_evidence() -> None:
    assert Exact().check({"a", "b"}, {"a", "b"}).ok
    missed = Exact().check({"a", "b"}, {"a", "c"})
    assert not missed.ok and missed.missing == ("b",) and missed.extra == ("c",)
    assert Exact().check(3, 3).ok and not Exact().check(3, 4).ok

    assert Superset().check({"a"}, {"a", "b"}).ok
    assert not Superset().check({"a", "z"}, {"a"}).ok

    assert Jaccard(at_least=0.5).check({"a", "b"}, {"a", "b", "c"}).ok
    assert not Jaccard(at_least=0.9).check({"a", "b"}, {"a", "c"}).ok

    assert Ratio(at_least=0.9).check("hello world", "hello worlds").ok
    assert not Ratio(at_least=0.9).check("hello world", "entirely different").ok

    assert Count(delta=1).check([1, 2, 3], [1, 2]).ok
    assert not Count(delta=0).check([1, 2, 3], [1, 2]).ok
    assert Count(lo=1, hi=3).check([], [1, 2]).ok and not Count(lo=5).check([], [1, 2]).ok

    assert Within(lo=0.0, hi=1.0).check(None, 0.5).ok
    assert not Within(lo=0.0, hi=1.0).check(None, 2.0).ok
    assert not Within(lo=0.0, hi=1.0).check(None, "not a number").ok


def test_count_refuses_an_ambiguous_declaration() -> None:
    """A tolerance that is both relative and absolute is neither (ADR 0046)."""
    with pytest.raises(ValueError, match="either delta="):
        Count(delta=1, lo=2)
    with pytest.raises(ValueError, match="either delta="):
        Count()


def test_a_set_tolerance_refuses_a_scalar_facet() -> None:
    assert not Superset().check(1, 2).ok
    assert not Jaccard(at_least=0.5).check(1, 2).ok
