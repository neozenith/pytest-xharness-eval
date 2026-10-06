"""The price curator (.github/scripts/curate_prices.py): selection, merge, close, render, run.

Every test here reads a small feed held in the test; nothing fetches the network. The script
is loaded from its path because it is repository tooling, not part of the package.
"""

from __future__ import annotations

# Standard Library
import importlib.util
import json
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.derive import pricing
from pytest_xharness_eval.model import registry

if TYPE_CHECKING:
    # Standard Library
    from types import ModuleType

SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "curate_prices.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("curate_prices", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["curate_prices"] = module  # dataclasses resolve their module by name
    spec.loader.exec_module(module)
    return module


cp = _load()


def _per_token(**per_mtok: float) -> dict[str, float]:
    """LiteLLM fields from USD-per-MTok values, as the feed states them (per token)."""
    return {k: v / 1e6 for k, v in per_mtok.items()}


FEED = {
    "sample_spec": {"note": "not a model"},
    "claude-sonnet-5-5": {
        "litellm_provider": "anthropic",
        "search_context_cost_per_query": {"search_context_size_low": 0.01},  # a tool fee: deliberately ignored
        **_per_token(
            input_cost_per_token=2,
            output_cost_per_token=10,
            cache_read_input_token_cost=0.2,
            cache_creation_input_token_cost=2.5,
            cache_creation_input_token_cost_above_1hr=4,
            input_cost_per_token_batches=1,  # a service tier the CLIs never request: ignored
        ),
    },
    "gpt-6-astra": {
        "litellm_provider": "openai",
        **_per_token(
            input_cost_per_token=10,
            output_cost_per_token=50,
            cache_read_input_token_cost=1,
            cache_creation_input_token_cost=12.5,
            input_cost_per_token_above_272k_tokens=20,
            output_cost_per_token_above_272k_tokens=75,
            cache_read_input_token_cost_above_272k_tokens=2,
            cache_creation_input_token_cost_above_272k_tokens=25,
            input_cost_per_token_above_272k_tokens_priority=40,
            input_cost_per_token_above_272k_tokens_ultrafast=60,
        ),
    },
    # Out of the watched families, or not first-party: ignored without a word.
    "gpt-5.5": {"litellm_provider": "openai", **_per_token(input_cost_per_token=5, output_cost_per_token=30)},
    "chatgpt/gpt-6-sol": {"litellm_provider": "chatgpt"},
    "us.anthropic.claude-sonnet-5-5": {
        "litellm_provider": "bedrock_converse",
        **_per_token(input_cost_per_token=2.2, output_cost_per_token=11),
    },
}


def test_select_keeps_watched_first_party_rows_in_usd_per_mtok() -> None:
    rows, unpriced, unrecognised = cp.select(FEED)
    assert [(r.harness, r.model) for r in rows] == [("claude", "claude-sonnet-5-5"), ("codex", "gpt-6-astra")]
    assert rows[0].tiers == {"input": 2.0, "output": 10.0, "cache_read": 0.2, "cache_write": 2.5, "cache_write_1h": 4.0}
    assert rows[0].long_context is None
    assert (unpriced, unrecognised) == ([], [])


def test_the_long_context_tier_is_data_with_its_threshold() -> None:
    """ADR 0051: the tier a call over 272K prompt tokens is billed at in full, not a comment."""
    rows, _, _ = cp.select(FEED)
    astra = rows[1]
    assert astra.tiers["cache_write_1h"] == astra.tiers["cache_write"] == 12.5
    assert astra.long_context == {
        cp.THRESHOLD: 272_000,
        "input": 20.0,
        "output": 75.0,
        "cache_read": 2.0,
        "cache_write": 25.0,
        "cache_write_1h": 25.0,  # OpenAI publishes no 1h tier, long or short
    }
    assert astra.comments == []


def test_a_cost_field_the_curator_does_not_model_stops_the_run() -> None:
    """A new pricing dimension must not vanish silently: that is how the long-context gap happened."""
    feed = {
        "gpt-6-sol": {
            "litellm_provider": "openai",
            **_per_token(input_cost_per_token=2, output_cost_per_token=10, input_cost_per_audio_token=40),
        }
    }
    with pytest.raises(cp.CurationError, match=r"does not model: \['input_cost_per_audio_token'\]"):
        cp.select(feed)


def test_long_context_fields_that_disagree_on_the_threshold_are_refused() -> None:
    feed = {
        "gpt-6-sol": {
            "litellm_provider": "openai",
            **_per_token(
                input_cost_per_token=2,
                output_cost_per_token=10,
                input_cost_per_token_above_272k_tokens=4,
                output_cost_per_token_above_200k_tokens=15,
            ),
        }
    }
    with pytest.raises(cp.CurationError, match=r"disagree on the threshold: \[200000, 272000\]"):
        cp.select(feed)


def _priced(provider: str) -> dict:
    return {"litellm_provider": provider, **_per_token(input_cost_per_token=1, output_cost_per_token=2)}


def test_a_future_release_is_curated_without_an_edit() -> None:
    """ADR 0052: scope is a boundary, so gpt-7 and a new Claude tier arrive on their own."""
    feed = {
        "gpt-7": _priced("openai"),
        "gpt-7.1-nova": _priced("openai"),
        "gpt-10-sol": _priced("openai"),
        "claude-nova-6": _priced("anthropic"),
    }
    rows, _, unrecognised = cp.select(feed)
    assert sorted(r.model for r in rows) == ["claude-nova-6", "gpt-10-sol", "gpt-7", "gpt-7.1-nova"]
    assert unrecognised == []


def test_below_the_floor_or_off_the_shape_is_out_of_scope_not_an_error() -> None:
    """Earlier generations and gpt-<word> sub-lines are outside the boundary: skipped, not refused."""
    feed = {
        k: _priced("openai") for k in ("gpt-5.5", "gpt-5.5-pro", "gpt-4o", "gpt-4o-mini", "gpt-image-2", "gpt-oss-120b")
    }
    assert cp.select(feed) == ([], [], [])


def test_generations_compare_numerically_not_as_text() -> None:
    assert cp.generation("5.10") > cp.generation("5.6") and cp.generation("10") > cp.generation("6")
    assert cp.generation("6") > cp.generation("5.6") and cp.generation("5.6") == (5, 6)


def test_an_id_no_grammar_fits_is_reported_not_guessed() -> None:
    """A dated OpenAI snapshot or a new Claude suffix is a new shape: the run must stop (ADR 0007)."""
    feed = {
        "gpt-6-astra-2026-09-03": {
            "litellm_provider": "openai",
            **_per_token(input_cost_per_token=10, output_cost_per_token=50),
        },
        "claude-opus-5-5-thinking": {
            "litellm_provider": "anthropic",
            **_per_token(input_cost_per_token=4, output_cost_per_token=20),
        },
        "gpt-6-sol": {"litellm_provider": "openai"},
    }
    rows, unpriced, unrecognised = cp.select(feed)
    assert rows == []
    assert unpriced == ["codex/gpt-6-sol"]
    assert unrecognised == ["claude/claude-opus-5-5-thinking", "codex/gpt-6-astra-2026-09-03"]


def test_merge_keeps_overrides_carries_vanished_rows_and_reports_reprices() -> None:
    old = {
        ("claude", "claude-sonnet-5-5"): cp.Row("claude", "claude-sonnet-5-5", {"input": 3.0, "output": 15.0}),
        ("codex", "gpt-6-astra"): cp.Row(
            "codex", "gpt-6-astra", {"input": 9.0, "output": 45.0}, comments=[f"{cp.KEEP_MARKER} (negotiated rate)"]
        ),
        ("codex", "gpt-6-gone"): cp.Row("codex", "gpt-6-gone", {"input": 1.0, "output": 2.0}, comments=["# hand note"]),
    }
    new, _, _ = cp.select(FEED)
    merged, report = cp.merge(new, old)
    by_key = {(r.harness, r.model): r for r in merged}
    (repriced,) = report["repriced"]
    assert repriced.startswith("claude/claude-sonnet-5-5 (") and "input 3.00->2.00" in repriced
    # A keep marker with a reason after it is still a keep marker (ADR 0006).
    assert report["kept"] == ["codex/gpt-6-astra"] and by_key[("codex", "gpt-6-astra")].tiers["input"] == 9.0
    assert report["carried"] == ["codex/gpt-6-gone"]
    assert by_key[("codex", "gpt-6-gone")].comments[-1].startswith("# Carried forward")
    assert cp.changed(report)


def test_a_gained_long_context_tier_is_a_reprice() -> None:
    new, _, _ = cp.select(FEED)
    astra = new[1]
    old = {("codex", "gpt-6-astra"): cp.Row("codex", "gpt-6-astra", dict(astra.tiers))}
    _, report = cp.merge([astra], old)
    (repriced,) = report["repriced"]
    assert "long_context.above_prompt_tokens –->272000" in repriced and "long_context.input –->20.00" in repriced


def test_an_unchanged_feed_is_not_a_change() -> None:
    new, _, _ = cp.select(FEED)
    old = {(r.harness, r.model): r for r in new}
    _, report = cp.merge(new, old)
    assert not cp.changed(report) and len(report["unchanged"]) == 2


def test_close_sets_effective_to_once_despite_the_header_naming_it() -> None:
    text = "# `effective_to` is omitted on the open file.\neffective_from = 2026-09-29\n"
    closed = cp.close(text, date(2026, 9, 30))
    assert "effective_to = 2026-09-30" in closed and closed.index("effective_from") < closed.index("effective_to =")
    with pytest.raises(cp.CurationError, match="already has an effective_to"):
        cp.close(closed, date(2026, 10, 1))


def test_render_is_a_record_the_plugin_loads_with_its_long_context_tier(tmp_path: Path) -> None:
    rows, _, _ = cp.select(FEED)
    path = tmp_path / "prices-20261001.toml"
    path.write_text(cp.render(rows, date(2026, 10, 1), "abc123", date(2026, 9, 30)), encoding="utf-8")
    loaded = {(r.harness, r.model): r for r in pricing.parse_record(path)}
    astra = loaded[("codex", "gpt-6-astra")]
    assert (astra.input, astra.output, astra.cache_write_1h) == (10.0, 50.0, 12.5)
    assert astra.long_context == pricing.LongContext(
        above_prompt_tokens=272_000, input=20.0, output=75.0, cache_read=2.0, cache_write=25.0, cache_write_1h=25.0
    )
    assert astra.interval == pricing.Interval(date(2026, 10, 1), None)
    assert loaded[("claude", "claude-sonnet-5-5")].long_context is None


@pytest.fixture
def prices_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A copy of the bundled records, with the script's package and staging paths pointed at tmp."""
    directory = tmp_path / "prices"
    shutil.copytree(cp.PRICES_DIR, directory)
    monkeypatch.setattr(cp, "PRICES_DIR", directory)
    monkeypatch.setattr(cp, "STAGING", tmp_path / "staging")
    return directory


def _feed_from_bundled(directory: Path, extra: dict[str, dict]) -> dict:
    """A feed that reproduces the open record exactly, long-context tiers included, plus ``extra`` rows."""
    feed: dict = dict(extra)
    open_record = cp.open_record(directory)
    assert open_record is not None
    for (harness, model), row in cp.read_rows(open_record).items():
        provider = {"claude": "anthropic", "codex": "openai"}[harness]
        derived = harness == "codex"  # the curator derives OpenAI's 1h tier; the feed never states it
        fields = {cp.LITELLM_FIELD[t]: v / 1e6 for t, v in row.tiers.items() if not (derived and t == "cache_write_1h")}
        if row.long_context:
            k = int(row.long_context[cp.THRESHOLD]) // 1000
            for t, v in row.long_context.items():
                if t != cp.THRESHOLD and not (derived and t == "cache_write_1h"):
                    fields[f"{cp.LITELLM_FIELD[t]}_above_{k}k_tokens"] = v / 1e6
        feed[model] = {"litellm_provider": provider, **fields}
    return feed


def test_a_run_with_nothing_changed_writes_nothing(prices_dir: Path, tmp_path: Path) -> None:
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps(_feed_from_bundled(prices_dir, {})), encoding="utf-8")
    before = sorted(p.name for p in prices_dir.iterdir())
    assert cp.main(["--feed", str(feed), "--date", "2099-01-01"]) == 0
    assert sorted(p.name for p in prices_dir.iterdir()) == before


def test_a_run_with_a_new_model_closes_the_open_record_and_adds_one(prices_dir: Path, tmp_path: Path) -> None:
    feed = tmp_path / "feed.json"
    extra = {
        "gpt-6-nova": {"litellm_provider": "openai", **_per_token(input_cost_per_token=3, output_cost_per_token=9)}
    }
    feed.write_text(json.dumps(_feed_from_bundled(prices_dir, extra)), encoding="utf-8")
    old = cp.open_record(prices_dir)
    assert old is not None
    assert cp.main(["--feed", str(feed), "--date", "2099-01-01", "--dry-run"]) == 0
    assert not (prices_dir / "prices-20990101.toml").exists()  # a dry run stages only
    assert cp.main(["--feed", str(feed), "--date", "2099-01-01"]) == 0
    assert "effective_to = 2099-01-01" in old.read_text(encoding="utf-8")
    table = pricing.PriceTable(tuple(pricing.load_records(prices_dir)))
    assert table.resolve("codex", "gpt-6-nova", date(2099, 1, 1)).input == 3.0
    # The long-context tiers survived the round trip into the new record.
    assert table.resolve("codex", "gpt-6-sol", date(2099, 1, 1)).long_context is not None


def test_an_empty_prices_directory_bootstraps_the_first_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty = tmp_path / "prices"
    empty.mkdir()
    monkeypatch.setattr(cp, "PRICES_DIR", empty)
    monkeypatch.setattr(cp, "STAGING", tmp_path / "staging")
    feed = tmp_path / "feed.json"
    source = json.loads(json.dumps(FEED))
    # Every catalogued model must price (ADR 0057), so the bootstrap feed carries their rows too.
    provider = {"claude": "anthropic", "codex": "openai"}
    for harness_name, spec in registry.catalogue():
        source[spec.id] = {
            "litellm_provider": provider[harness_name],
            **_per_token(input_cost_per_token=1, output_cost_per_token=2),
        }
    feed.write_text(json.dumps(source), encoding="utf-8")
    assert cp.main(["--feed", str(feed), "--date", "2026-09-29"]) == 0
    assert [p.name for p in empty.iterdir()] == ["prices-20260929.toml"]


def test_a_date_not_after_the_open_record_is_refused(prices_dir: Path, tmp_path: Path) -> None:
    feed = tmp_path / "feed.json"
    extra = {
        "gpt-6-nova": {"litellm_provider": "openai", **_per_token(input_cost_per_token=3, output_cost_per_token=9)}
    }
    feed.write_text(json.dumps(_feed_from_bundled(prices_dir, extra)), encoding="utf-8")
    with pytest.raises(cp.CurationError, match="must be after the open record"):
        cp.main(["--feed", str(feed), "--date", "2026-09-29"])
