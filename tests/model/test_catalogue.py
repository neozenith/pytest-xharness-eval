"""``model.catalogue``: the supported models, their line, frozen family tier and release date (ADR 0057)."""

# Standard Library
from datetime import date

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.derive import pricing
from pytest_xharness_eval.model import registry
from pytest_xharness_eval.model.catalogue import Catalogue, CatalogueError, ModelSpec, parse_model_line

OPUS = ModelSpec(id="claude-opus-5", line="opus", family_tier=3, released=date(2026, 7, 24))


def test_a_model_line_parses_into_a_harness_and_a_spec() -> None:
    harness_name, spec = parse_model_line("codex/gpt-7-sol: line=sol tier=3 released=2027-01-15")
    assert harness_name == "codex"
    assert spec == ModelSpec(id="gpt-7-sol", line="sol", family_tier=3, released=date(2027, 1, 15))


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("gpt-7: line=sol tier=3 released=2027-01-15", "expected"),
        ("codex/gpt-7: line=sol tier=3", "missing"),
        ("codex/gpt-7: line=sol tier=3 released=2027-01-15 price=1", "unknown"),
        ("codex/gpt-7: line=sol tier=three released=2027-01-15", "invalid literal"),
        ("codex/gpt-7: line=sol tier=0 released=2027-01-15", "1 or more"),
        ("codex/gpt-7: line=sol tier=3 released=2027-13-01", "month"),
    ],
)
def test_a_malformed_model_line_is_refused(text: str, match: str) -> None:
    with pytest.raises(CatalogueError, match=match):
        parse_model_line(text)


def test_a_project_line_adds_a_model_and_wins_over_the_bundled_spec() -> None:
    catalogue = Catalogue.of(
        [("claude", OPUS)],
        [
            "claude/claude-opus-5: line=opus tier=4 released=2026-07-24",
            "claude/claude-opus-6: line=opus tier=3 released=2027-02-01",
        ],
    )
    assert catalogue.require("claude", "claude-opus-5").family_tier == 4
    assert catalogue.require("claude", "claude-opus-6").released == date(2027, 2, 1)


def test_a_line_for_an_unknown_harness_is_refused() -> None:
    with pytest.raises(CatalogueError, match="unknown harness 'gemini'"):
        Catalogue.of([("claude", OPUS)], ["gemini/pro: line=pro tier=3 released=2026-01-01"])


def test_an_uncatalogued_model_names_the_line_that_would_add_it() -> None:
    catalogue = Catalogue.of([("claude", OPUS)])
    assert catalogue.get("claude", "claude-opus-4-5") is None
    with pytest.raises(CatalogueError, match="xharness_models line 'claude/claude-opus-4-5: line="):
        catalogue.require("claude", "claude-opus-4-5")


def test_iteration_keeps_harness_order_with_project_models_after_the_bundled_ones() -> None:
    codex = ModelSpec(id="gpt-5.6-sol", line="sol", family_tier=3, released=date(2026, 7, 9))
    catalogue = Catalogue.of(
        [("claude", OPUS), ("codex", codex)], ["claude/claude-x: line=x tier=1 released=2026-01-01"]
    )
    assert [(h, s.id) for h, s in catalogue] == [
        ("claude", "claude-opus-5"),
        ("claude", "claude-x"),
        ("codex", "gpt-5.6-sol"),
    ]


def test_every_bundled_model_is_priced_today_and_tiers_are_contiguous_per_harness() -> None:
    """The catalogue and the open price record move together, and no harness skips a tier."""
    table = pricing.load_table()
    catalogue = registry.catalogue()
    table.validate_matrix([f"{h}/{s.id}" for h, s in catalogue], None)
    for harness_name in registry.names():
        tiers = {s.family_tier for h, s in catalogue if h == harness_name}
        assert tiers == set(range(1, max(tiers) + 1)), harness_name
