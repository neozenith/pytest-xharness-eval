"""``derive.pricing``: dated records, per-call long-context pricing, project lines (ADR 0050, ADR 0051)."""

# Standard Library
import textwrap
from datetime import date
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import (
    Call,
    CostStatus,
    RunResult,
    Usage,
)
from pytest_xharness_eval import harness as harnesses
from pytest_xharness_eval.derive import pricing
from pytest_xharness_eval.model.runresult import Subagent
from tests.support import DAY, _result


def test_bundled_table_prices_each_tier_separately() -> None:
    table = pricing.load_table()
    r = pricing.price(_result("claude-opus-5", Usage(1_000_000, 1_000_000, 1_000_000, 1_000_000)), table, DAY)
    assert r.cost_status is CostStatus.PRICED and r.cost_status == "priced"  # a StrEnum on the wire
    # An untagged cache write prices at the 5-minute rate.
    assert r.estimated_cost_usd == pytest.approx(5.0 + 25.0 + 0.5 + 6.25)
    # Provenance rides with the estimate (ADR 0021): the row, the file, the interval, the rates, the time.
    applied = r.rates_applied
    assert applied is not None
    assert (applied.harness, applied.model, applied.unit) == ("claude", "claude-opus-5", "usd_per_mtok")
    assert applied.source.endswith("prices-20260929.toml")
    # The record covering DAY; a later `make prices` closes it, so its end is not pinned (ADR 0050).
    assert applied.effective_from == "2026-09-29"
    assert applied.effective_to is None or applied.effective_to > DAY.isoformat()
    # Rates are USD per MTok on the wire, exactly as the record states them (ADR 0050).
    assert applied.cache_write_1h == 10.0 and applied.applied_at.endswith("+00:00")
    assert r.cost_by_tier == {
        "input": 5.0,
        "output": 25.0,
        "cache_read": 0.5,
        "cache_write_5m": 6.25,
        "cache_write_1h": 0.0,
    }


def test_cache_writes_price_by_ttl() -> None:
    """Claude Code writes 1-hour cache entries at 2x input; the log says so and the price follows (ADR 0019)."""
    table = pricing.load_table()
    one_hour = Usage(cache_write_tokens=1_000_000, cache_write_1h_tokens=1_000_000)
    assert pricing.price(_result("claude-opus-5", one_hour), table, DAY).estimated_cost_usd == pytest.approx(10.0)
    mixed = Usage(cache_write_tokens=1_000_000, cache_write_1h_tokens=400_000, cache_write_5m_tokens=100_000)
    r = pricing.price(_result("claude-opus-5", mixed), table, DAY)
    # 400k at 1h, 100k tagged 5m plus 500k untagged at the 5m rate.
    assert r.cost_by_tier["cache_write_1h"] == pytest.approx(4.0)
    assert r.cost_by_tier["cache_write_5m"] == pytest.approx(600_000 * 6.25 / 1e6)
    # A row without cache_write_1h gets the Anthropic 2.0 / 1.25 ratio.
    table = pricing.load_table(rows=["claude/m: input=1.0 output=1.0 cache_write=2.0"])
    row = table.get("claude", "m")
    assert row is not None and row.cache_write_1h == pytest.approx(3.2)


def test_per_mtok_rates_divide_once_so_round_rates_give_round_costs() -> None:
    """Multiplying by the published $/MTok and dividing once avoids the error a pre-divided rate carries (ADR 0050).

    ``3_000_000 * 1e-7`` is ``0.30000000000000004``; ``3_000_000 * 0.10 / 1e6`` is ``0.3``.
    Fewer representation errors, not none: the breakdown is unrounded here on purpose.
    """
    table = pricing.load_table(rows=["codex/m: input=0.10 output=1.00 cache_read=0.125"])
    row = table.resolve("codex", "m", DAY)
    tiers = pricing.tier_costs(Usage(input_tokens=3_000_000, cache_read_tokens=170_000), row)
    assert tiers["input"] == 0.3 and tiers["cache_read"] == 0.02125


def test_cache_reads_are_not_billed_at_the_input_rate() -> None:
    table = pricing.load_table()
    codex = "codex"
    flat = pricing.price(_result("gpt-5.6-sol", Usage(input_tokens=200_000), codex), table, DAY).estimated_cost_usd
    tiered = pricing.price(
        _result("gpt-5.6-sol", Usage(input_tokens=30_000, cache_read_tokens=170_000), codex), table, DAY
    ).estimated_cost_usd
    assert flat is not None and tiered is not None
    assert tiered < flat / 3


def test_resolve_is_prefix_tolerant_both_ways_within_a_harness() -> None:
    table = pricing.load_table()
    assert table.resolve("claude", "claude-opus-5[1m]", DAY) == table.get("claude", "claude-opus-5", DAY)
    # A row key longer than the id asked for: "gpt-5" is a prefix of every gpt-5.6 row.
    assert table.resolve("codex", "gpt-5", DAY).model.startswith("gpt-5.6")


def test_a_row_is_found_only_under_the_harness_it_is_grouped_by() -> None:
    """Rows are keyed by (harness, model): a codex model is not priced for a claude run (ADR 0050)."""
    table = pricing.load_table()
    with pytest.raises(pricing.PricingError, match="no price row for claude/gpt-6-sol"):
        table.resolve("claude", "gpt-6-sol", DAY)


def test_unknown_model_raises_rather_than_pricing_zero() -> None:
    table = pricing.load_table()
    with pytest.raises(pricing.PricingError, match="Refusing to price as zero"):
        table.resolve("claude", "mystery-model", DAY)
    with pytest.raises(pricing.PricingError, match=r"unpriced models in matrix: \['codex/mystery-model/high'\]"):
        table.validate_matrix(["claude/claude-opus-5/high", "codex/mystery-model/high"], DAY)


def test_a_run_before_every_record_is_unpriced_not_zero() -> None:
    """A date no record covers stops at resolution rather than borrowing a neighbour's rates (ADR 0007)."""
    table = pricing.load_table()
    with pytest.raises(pricing.PricingError, match="in effect on 2026-01-01"):
        table.resolve("claude", "claude-opus-5", date(2026, 1, 1))


def _record(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_dated_records_choose_the_rates_in_effect_on_the_run_day(tmp_path: Path) -> None:
    """Consecutive records meet at a boundary day that belongs to the newer one: ``[from, to)`` (ADR 0050)."""
    _record(
        tmp_path,
        "prices-20260101.toml",
        """
        effective_from = 2026-01-01
        effective_to = 2026-06-01
        [claude."claude-x"]
        input = 1.0
        output = 2.0
        """,
    )
    _record(
        tmp_path,
        "prices-20260601.toml",
        """
        effective_from = 2026-06-01
        [claude."claude-x"]
        input = 3.0
        output = 4.0
        """,
    )
    table = pricing.load_table(tmp_path)
    assert table.resolve("claude", "claude-x", date(2026, 5, 31)).input == 1.0
    assert table.resolve("claude", "claude-x", date(2026, 6, 1)).input == 3.0
    # A capture with no datable stamp prices from the record still open.
    assert table.resolve("claude", "claude-x", None).input == 3.0
    old = table.resolve("claude", "claude-x", date(2026, 3, 1)).applied("t")
    assert (old.effective_from, old.effective_to) == ("2026-01-01", "2026-06-01")


@pytest.mark.parametrize(
    ("name", "body", "match"),
    [
        ("prices.toml", "effective_from = 2026-01-01\n", "named prices-YYYYMMDD.toml"),
        ("prices-20260101.toml", "[claude.m]\ninput = 1\noutput = 1\n", "must be TOML dates"),
        ("prices-20260101.toml", 'effective_from = "2026-01-01"\n', "must be TOML dates"),
        ("prices-20260102.toml", "effective_from = 2026-01-01\n", "the name says 20260102"),
        ("prices-20260101.toml", "effective_from = 2026-01-01\neffective_to = 2026-01-01\n", "is not after"),
        ("prices-20260101.toml", "effective_from = 2026-01-01\n[cursor.m]\ninput = 1\noutput = 1\n", "unknown harness"),
        ("prices-20260101.toml", "effective_from = 2026-01-01\n[claude.m]\ninput = 1\n", "missing required tier"),
        ("prices-20260101.toml", "effective_from = 2026-01-01\n[claude.m]\ninput = 1e-6\noutput = 1\n", "per-token"),
        ("prices-20260101.toml", "effective_from = 2026-01-01\n[claude.m]\ninput = 1\noutput = 1\nturbo = 1\n", "tier"),
        ("prices-20260101.toml", "effective_from = 2026-01-01\nclaude = 3\n", "must be a table of models"),
    ],
)
def test_a_malformed_record_is_refused(tmp_path: Path, name: str, body: str, match: str) -> None:
    with pytest.raises(pricing.PricingError, match=match):
        pricing.parse_record(_record(tmp_path, name, body))


def test_overlapping_records_are_refused(tmp_path: Path) -> None:
    _record(tmp_path, "prices-20260101.toml", "effective_from = 2026-01-01\n[claude.m]\ninput = 1\noutput = 1\n")
    _record(tmp_path, "prices-20260601.toml", "effective_from = 2026-06-01\n[claude.m]\ninput = 2\noutput = 2\n")
    with pytest.raises(pricing.PricingError, match="overlap: prices-20260101.toml and prices-20260601.toml"):
        pricing.load_table(tmp_path)


def test_the_curated_record_models_each_providers_long_context_tier() -> None:
    """OpenAI's 272K tier and Claude Sonnet 4.5's 200K tier are data, not comments (ADR 0051)."""
    table = pricing.load_table()
    sol = table.resolve("codex", "gpt-6-sol", DAY).long_context
    assert sol == pricing.LongContext(
        above_prompt_tokens=272_000, input=4.0, output=15.0, cache_read=0.4, cache_write=5.0, cache_write_1h=5.0
    )
    sonnet_45 = table.resolve("claude", "claude-sonnet-4-5", DAY).long_context
    assert sonnet_45 is not None and (sonnet_45.above_prompt_tokens, sonnet_45.input, sonnet_45.output) == (
        200_000,
        6.0,
        22.5,
    )
    # Anthropic bills its current models' whole window at one rate: no tier at all.
    assert table.resolve("claude", "claude-sonnet-5-5", DAY).long_context is None


def _with_calls(model: str, usages: list[Usage], harness: str = "codex") -> RunResult:
    """A run whose usage is folded from ``usages``, one call each: what an adapter builds."""
    r = _result(model, Usage.total(usages), harness)
    r.calls = [Call(n=i + 1, at="t", usage=u) for i, u in enumerate(usages)]
    return r


def test_each_call_is_billed_at_the_tier_its_own_prompt_selects() -> None:
    """OpenAI: "Prompts with more than 272K input tokens are priced at 2x input and cache rates
    and 1.5x output for the full request." At exactly 272,000 the base tier still applies (ADR 0051).
    """
    at_threshold = Usage(input_tokens=272_000, output_tokens=1_000)
    over = Usage(input_tokens=200_001, cache_read_tokens=72_000, output_tokens=1_000)  # cached input counts
    r = pricing.price(_with_calls("gpt-6-sol", [at_threshold, over]), pricing.load_table(), DAY)
    base = 272_000 * 2.0 / 1e6 + 1_000 * 10.0 / 1e6
    long = 200_001 * 4.0 / 1e6 + 72_000 * 0.4 / 1e6 + 1_000 * 15.0 / 1e6
    assert r.estimated_cost_usd == pytest.approx(base + long)
    assert r.long_context_calls == 1
    assert r.rates_applied is not None and r.rates_applied.long_context is not None
    assert r.rates_applied.long_context.above_prompt_tokens == 272_000
    # Pricing the summed usage instead would put both calls over the threshold: the error this closes.
    summed = pricing.CostEstimate.of([at_threshold + over], pricing.load_table().resolve("codex", "gpt-6-sol", DAY))
    assert r.estimated_cost_usd is not None
    assert summed.long_context_calls == 1 and summed.total_usd > r.estimated_cost_usd


def test_subagent_calls_cross_the_threshold_on_their_own_prompts() -> None:
    primary = Usage(input_tokens=10_000, output_tokens=100)
    spawned = Usage(input_tokens=300_000, output_tokens=100)
    r = _with_calls("gpt-6-sol", [primary])
    r.subagents = [Subagent.folded([Call(n=1, at="t", usage=spawned)], agent="a", id="x", log="l")]
    r.usage = primary + spawned
    priced = pricing.price(r, pricing.load_table(), DAY)
    assert priced.long_context_calls == 1
    assert priced.estimated_cost_usd == pytest.approx(
        10_000 * 2.0 / 1e6 + 100 * 10.0 / 1e6 + 300_000 * 4.0 / 1e6 + 100 * 15.0 / 1e6
    )


def test_usage_no_call_accounts_for_is_still_billed_at_the_base_tier() -> None:
    """A run without a ledger cannot blame a call for crossing a threshold, so it prices at base, never zero."""
    r = pricing.price(_result("gpt-6-sol", Usage(input_tokens=500_000), "codex"), pricing.load_table(), DAY)
    assert (r.estimated_cost_usd, r.long_context_calls) == (pytest.approx(1.0), 0)
    calls, residual = pricing.calls_of(_with_calls("gpt-6-sol", [Usage(input_tokens=5)]))
    assert calls == [Usage(input_tokens=5)] and residual == Usage()


def test_a_row_without_a_long_context_tier_bills_every_call_at_base() -> None:
    r = pricing.price(
        _with_calls("claude-sonnet-5-5", [Usage(input_tokens=900_000)], "claude"), pricing.load_table(), DAY
    )
    assert (r.estimated_cost_usd, r.long_context_calls) == (pytest.approx(1.8), 0)


def test_a_record_row_states_its_long_context_tier_as_a_sub_table(tmp_path: Path) -> None:
    path = _record(
        tmp_path,
        "prices-20260101.toml",
        """
        effective_from = 2026-01-01
        [codex."m"]
        input = 1.0
        output = 2.0
        [codex."m".long_context]
        above_prompt_tokens = 100000
        input = 2.0
        output = 3.0
        """,
    )
    (row,) = pricing.parse_record(path)
    assert row.long_context == pricing.LongContext(
        above_prompt_tokens=100_000, input=2.0, output=3.0, cache_read=2.0, cache_write=2.0, cache_write_1h=3.2
    )


@pytest.mark.parametrize(
    ("long_table", "match"),
    [
        ("input = 2.0\noutput = 3.0\n", "above_prompt_tokens must be a whole number"),
        ('above_prompt_tokens = "272k"\ninput = 2.0\noutput = 3.0\n', "above_prompt_tokens must be a whole number"),
        ("above_prompt_tokens = 0\ninput = 2.0\noutput = 3.0\n", "positive token count"),
        ("above_prompt_tokens = 1000\ninput = 2.0\n", "missing required tier"),
        ("above_prompt_tokens = 1000\ninput = 2.0\noutput = 3.0\nturbo = 1\n", "unknown tier"),
    ],
)
def test_a_malformed_long_context_tier_is_refused(tmp_path: Path, long_table: str, match: str) -> None:
    body = 'effective_from = 2026-01-01\n[codex."m"]\ninput = 1\noutput = 1\n[codex."m".long_context]\n' + long_table
    with pytest.raises(pricing.PricingError, match=match):
        pricing.parse_record(_record(tmp_path, "prices-20260101.toml", body))


def test_a_price_line_states_a_long_context_tier_with_long_keys() -> None:
    (row,) = pricing.parse_price_lines(
        ["codex/m: input=1 output=2 long_context_above=272000 long_input=2 long_output=3 long_cache_read=0.2"]
    )
    assert row.long_context == pricing.LongContext(
        above_prompt_tokens=272_000, input=2.0, output=3.0, cache_read=0.2, cache_write=2.0, cache_write_1h=3.2
    )


@pytest.mark.parametrize(
    ("line", "match"),
    [
        ("codex/m: input=1 output=2 long_input=2 long_output=3", "need long_context_above"),
        ("codex/m: input=1 output=2 long_context_above=272k long_input=2 long_output=3", "not a whole number"),
        ("codex/m: input=1 output=2 long_context_above=272000 long_input=2", r"needs \['long_output'\]"),
        ("codex/m: input=1 output=2 long_context_above=0 long_input=2 long_output=3", "positive token count"),
    ],
)
def test_a_malformed_long_context_line_is_refused(line: str, match: str) -> None:
    with pytest.raises(pricing.PricingError, match=match):
        pricing.parse_price_lines([line])


def test_claude_sonnet_5_5_is_priced_from_the_record_that_opened_for_it() -> None:
    """Verified 2026-09-29: $2 in, $10 out, $0.20 cache read, $2.50 / $4 cache writes per MTok."""
    row = pricing.load_table().get("claude", "claude-sonnet-5-5", DAY)
    assert row is not None and row.source.endswith("prices-20260929.toml")
    assert (row.input, row.output, row.cache_read, row.cache_write, row.cache_write_1h) == (2.0, 10.0, 0.2, 2.5, 4.0)


def test_every_bundled_record_loads_and_one_is_still_open() -> None:
    """The shipped records are well-formed, and today's sweep has rates to price from."""
    rows = pricing.load_records()
    assert rows and all(r.source.startswith(str(pricing.PRICES_DIR)) for r in rows)
    assert any(r.interval.end is None for r in rows)
    assert {r.harness for r in rows} <= set(harnesses.names())


def test_price_lines_layer_on_top_of_the_bundled_records() -> None:
    """`xharness_prices` lines are USD per MTok in pytest's `name: text` idiom (ADR 0030, ADR 0050)."""
    table = pricing.load_table(
        rows=["# a comment", "", "claude/claude-opus-5: input=1.0 output=1.0", "codex/new-model: input=2.0 output=3.0"]
    )
    # Cache tiers default to input; every row remembers its pair and that the ini supplied it.
    assert table.resolve("claude", "claude-opus-5", DAY) == pricing.Rates(
        input=1.0,
        output=1.0,
        cache_read=1.0,
        cache_write=1.0,
        cache_write_1h=1.6,
        long_context=None,
        harness="claude",
        model="claude-opus-5",
        source="xharness_prices",
        interval=pricing.Interval(None, None),
    )
    sol = table.resolve("codex", "gpt-5.6-sol", DAY)
    assert sol.source.endswith("prices-20260929.toml")  # bundled rows survive
    assert table.resolve("codex", "new-model", DAY).output == 3.0
    assert pricing.load_table(rows=[]) == pricing.load_table()


def test_a_dated_price_line_overrides_only_inside_its_interval() -> None:
    table = pricing.load_table(rows=["claude/claude-opus-5: input=9 output=9 from=2026-09-01 to=2026-10-01"])
    assert table.resolve("claude", "claude-opus-5", date(2026, 9, 15)).input == 9.0
    assert table.resolve("claude", "claude-opus-5", date(2026, 10, 1)).input == 5.0  # the bundled row again
    assert table.resolve("claude", "claude-opus-5", date(2026, 9, 15)).applied("t").effective_to == "2026-10-01"


@pytest.mark.parametrize(
    ("line", "match"),
    [
        ("claude/claude-opus-5 input=1 output=1", "expected"),
        ("claude/claude-opus-5:", "expected"),
        (": input=1 output=1", "selector"),
        ("claude-opus-5: input=1 output=1", r"'<harness>/<model>'"),
        ("cursor/m: input=1 output=1", "unknown harness 'cursor'"),
        ("claude/m: input=1 output=1 turbo=9", "unknown key"),
        ("claude/m: input=one output=1", "not a number"),
        ("claude/m: input=1 cache_read=2", r"missing required tier\(s\) \['output'\]"),
        ("claude/m: input=5.0e-6 output=25", "looks like a per-token rate"),
        ("claude/m: input=1 output=-3", "looks like a per-token rate"),
        ("claude/m: input=1 output=1 from=yesterday", "not an ISO date"),
        ("claude/m: input=1 output=1 from=2026-09-01 to=2026-08-01", "is not after"),
    ],
)
def test_malformed_price_lines_stop_before_any_spend(line: str, match: str) -> None:
    with pytest.raises(pricing.PricingError, match=match):
        pricing.parse_price_lines([line])


def test_two_price_lines_for_one_pair_may_not_overlap_in_time() -> None:
    with pytest.raises(pricing.PricingError, match="overlap in time"):
        pricing.parse_price_lines(["claude/m: input=1 output=1", "claude/m: input=2 output=2 from=2026-09-01"])
    rows = pricing.parse_price_lines(
        ["claude/m: input=1 output=1 to=2026-09-01", "claude/m: input=2 output=2 from=2026-09-01"]
    )
    assert [r.input for r in rows] == [1.0, 2.0]
