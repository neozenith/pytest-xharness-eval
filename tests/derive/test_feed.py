"""``derive.feed``: LiteLLM entries into price rows and dated records, shared by curator and live pricing (ADR 0060)."""

# Standard Library
import json
from datetime import date
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.derive import feed, pricing
from pytest_xharness_eval.derive.catalogue import Feed

FEEDS = (
    Feed(harness="claude", provider="anthropic", one_hour_is_five_minute=False),
    Feed(harness="codex", provider="openai", one_hour_is_five_minute=True),
)
OPENAI = {
    "litellm_provider": "openai",
    "input_cost_per_token": 2e-06,
    "output_cost_per_token": 1.2e-05,
    "cache_read_input_token_cost": 2e-07,
    "cache_creation_input_token_cost": 2.5e-06,
}


def test_an_entry_converts_to_usd_per_mtok_and_repeats_a_missing_one_hour_tier() -> None:
    row = feed.row_from("codex", "gpt-7-terra", OPENAI, one_hour_is_five_minute=True)
    assert row is not None
    assert row.tiers == {"input": 2.0, "output": 12.0, "cache_read": 0.2, "cache_write": 2.5, "cache_write_1h": 2.5}


def test_an_entry_without_input_and_output_rates_is_no_row() -> None:
    assert feed.row_from("codex", "gpt-7", {"litellm_provider": "openai"}, one_hour_is_five_minute=True) is None


def test_a_cost_field_nobody_models_stops_the_write() -> None:
    """A new pricing dimension must not vanish silently (ADR 0051)."""
    with pytest.raises(feed.FeedError, match="does not model"):
        feed.row_from("codex", "gpt-7", {**OPENAI, "input_cost_per_audio_token": 1e-05}, one_hour_is_five_minute=True)


def test_live_rows_match_the_exact_id_and_the_harness_provider_only() -> None:
    entries = {
        "gpt-7-terra": OPENAI,
        "gpt-7-sol": {**OPENAI, "litellm_provider": "azure"},  # a host's row is never first-party
    }
    rows = feed.live_rows([("codex", "gpt-7-terra"), ("codex", "gpt-7-sol"), ("codex", "gpt-7-luna")], entries, FEEDS)
    assert [(r.harness, r.model) for r in rows] == [("codex", "gpt-7-terra")]


def test_a_live_record_round_trips_through_the_plugins_own_loader(tmp_path: Path) -> None:
    rows = feed.live_rows([("codex", "gpt-7-terra")], {"gpt-7-terra": OPENAI}, FEEDS)
    path = feed.write_live_record(tmp_path / "pricing", rows, date(2026, 10, 7), "feed.json", ["claude", "codex"])
    assert path.name == "prices-20261007.toml"
    (loaded,) = pricing.parse_record(path)
    assert (loaded.harness, loaded.model, loaded.input, loaded.output) == ("codex", "gpt-7-terra", 2.0, 12.0)


def test_a_later_day_closes_the_open_live_record_and_carries_its_rows(tmp_path: Path) -> None:
    """Every day a run was stamped with keeps resolving to the rates it had (ADR 0050)."""
    pricing_dir = tmp_path / "pricing"
    first = feed.live_rows([("codex", "gpt-7-terra")], {"gpt-7-terra": OPENAI}, FEEDS)
    feed.write_live_record(pricing_dir, first, date(2026, 10, 7), "feed.json", ["codex"])
    second = feed.live_rows([("codex", "gpt-7-luna")], {"gpt-7-luna": OPENAI}, FEEDS)
    feed.write_live_record(pricing_dir, second, date(2026, 10, 9), "feed.json", ["codex"])
    table = pricing.PriceTable(tuple(pricing.load_records(pricing_dir)))
    assert table.get("codex", "gpt-7-terra", date(2026, 10, 8)) is not None
    assert table.get("codex", "gpt-7-terra", date(2026, 10, 9)) is not None  # carried forward
    assert table.get("codex", "gpt-7-luna", date(2026, 10, 8)) is None  # not priced before it was found


def test_the_same_day_adds_rows_to_the_open_record_in_place(tmp_path: Path) -> None:
    pricing_dir = tmp_path / "pricing"
    for model in ("gpt-7-terra", "gpt-7-luna"):
        rows = feed.live_rows([("codex", model)], {model: OPENAI}, FEEDS)
        feed.write_live_record(pricing_dir, rows, date(2026, 10, 7), "feed.json", ["codex"])
    assert [p.name for p in pricing_dir.iterdir()] == ["prices-20261007.toml"]
    assert {r.model for r in pricing.load_records(pricing_dir)} == {"gpt-7-terra", "gpt-7-luna"}


def test_a_feed_loads_from_a_local_path_and_must_be_an_object(tmp_path: Path) -> None:
    good, bad = tmp_path / "good.json", tmp_path / "bad.json"
    good.write_text(json.dumps({"gpt-7": OPENAI}), encoding="utf-8")
    bad.write_text("[]", encoding="utf-8")
    assert feed.load_feed(str(good)) == {"gpt-7": OPENAI}
    with pytest.raises(feed.FeedError, match="JSON object"):
        feed.load_feed(str(bad))
