"""LiteLLM's price feed, read into dated price records: shared by the curator and live pricing (ADR 0060).

Two writers turn LiteLLM's ``model_prices_and_context_window.json`` into the plugin's dated
``prices-YYYYMMDD.toml`` records, and they must not disagree on how:

* ``make prices`` (``.github/scripts/curate_prices.py``) curates the bundled records under
  ``derive/prices/`` from a pinned commit of the feed, for every watched family (ADR 0051).
* **Live pricing** fills a gap at collection. A matrix entry for a catalogued model with no
  price row is looked up in the feed, and the rates found are written as a dated record
  under ``<cache>/pricing/``. That record is read back by the sweep and by every later
  replay, so a run priced live is re-priced identically (ADR 0050).

Both convert a feed entry with :func:`row_from` and write a record with :func:`render`, so
the rules ADR 0051 set stand for both: every published rate is modelled, a long-context
tier is data, and a cost field neither modelled nor deliberately ignored stops the write.
"""

from __future__ import annotations

# Standard Library
import json
import re
import tomllib
import urllib.request
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterable, Sequence
    from datetime import date
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.derive.catalogue import Feed

#: The feed's current version: what live pricing reads when nothing pins a commit.
FEED_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"

TIERS = ("input", "output", "cache_read", "cache_write", "cache_write_1h")
LONG_CONTEXT = "long_context"
THRESHOLD = "above_prompt_tokens"

# Our tier -> LiteLLM's per-token field. A long-context tier is the same field plus
# ``_above_<N>k_tokens``, where N thousand prompt tokens is the threshold.
LITELLM_FIELD = {
    "input": "input_cost_per_token",
    "output": "output_cost_per_token",
    "cache_read": "cache_read_input_token_cost",
    "cache_write": "cache_creation_input_token_cost",
    "cache_write_1h": "cache_creation_input_token_cost_above_1hr",
}
LONG_FIELD = re.compile(rf"(?P<field>{'|'.join(LITELLM_FIELD.values())})_above_(?P<k>\d+)k_tokens")
# Cost fields deliberately not modelled, and why. The service-tier suffixes are rates the
# harness CLIs never request (batch, flex, priority and ultrafast processing); the search fee is billed
# per web-search query by a tool, not per token.
IGNORED_SUFFIXES = ("_batches", "_flex", "_priority", "_ultrafast")
IGNORED_FIELDS = frozenset({"search_context_cost_per_query"})


class FeedError(RuntimeError):
    """A condition neither writer will guess past: a feed or record it cannot read faithfully."""


@dataclass
class Row:
    """One price row in USD per MTok: base tiers, an optional long-context tier, and its comments."""

    harness: str
    model: str
    tiers: dict[str, float]
    long_context: dict[str, float] | None = None  # THRESHOLD plus the long-context tiers
    comments: list[str] = field(default_factory=list)

    def rates(self) -> dict[str, float]:
        """Every rate the row states, long-context ones prefixed: what a re-price is judged on."""
        long = {f"{LONG_CONTEXT}.{k}": v for k, v in (self.long_context or {}).items()}
        return {**self.tiers, **long}


# -- the feed -------------------------------------------------------------------------


def load_feed(source: str) -> dict[str, Any]:
    """The feed at ``source``: an ``http(s)://`` or ``file://`` URL, or a local path."""
    url = source if "://" in source else f"file://{source}"
    request = urllib.request.Request(url, headers={"User-Agent": "pytest-xharness-eval"})
    with urllib.request.urlopen(request, timeout=60) as resp:
        feed = json.load(resp)
    if not isinstance(feed, dict):
        raise FeedError(f"{source}: the price feed is a JSON object keyed by model id")
    return feed


def per_mtok(value: object) -> float | None:
    """A per-token rate as USD per MTok, rounded past float noise (3e-06 -> 3.0)."""
    return round(float(value) * 1_000_000, 6) if isinstance(value, int | float) else None


def unmodelled_fields(entry: dict[str, Any]) -> list[str]:
    """Cost fields on ``entry`` neither writer models nor deliberately ignores."""
    modelled = set(LITELLM_FIELD.values())
    return sorted(
        k
        for k in entry
        if "cost" in k
        and k not in modelled
        and k not in IGNORED_FIELDS
        and not k.endswith(IGNORED_SUFFIXES)
        and not LONG_FIELD.fullmatch(k)
    )


def long_context_of(name: str, entry: dict[str, Any], one_hour_is_five_minute: bool) -> dict[str, float] | None:
    """The long-context tier from ``*_above_<N>k_tokens`` fields: one threshold, all tiers at it."""
    found: dict[str, float] = {}
    thresholds = set()
    by_field = {v: k for k, v in LITELLM_FIELD.items()}
    for key, value in entry.items():
        m = LONG_FIELD.fullmatch(key)
        if m and (rate := per_mtok(value)) is not None:
            thresholds.add(int(m.group("k")) * 1000)  # LiteLLM reads "272k" as 272,000
            found[by_field[m.group("field")]] = rate
    if not found:
        return None
    if len(thresholds) != 1:
        raise FeedError(f"{name}: long-context fields disagree on the threshold: {sorted(thresholds)}")
    if "input" not in found or "output" not in found:
        raise FeedError(f"{name}: a long-context tier needs input and output rates, got {found}")
    if "cache_write_1h" not in found and "cache_write" in found and one_hour_is_five_minute:
        found["cache_write_1h"] = found["cache_write"]
    return {THRESHOLD: float(thresholds.pop()), **{t: found[t] for t in TIERS if t in found}}


def row_from(harness: str, model: str, entry: dict[str, Any], one_hour_is_five_minute: bool) -> Row | None:
    """One feed entry as a row in USD per MTok, or None when it has no per-token input and output rate."""
    name = f"{harness}/{model}"
    unmodelled = unmodelled_fields(entry)
    if unmodelled:
        raise FeedError(f"{name}: cost fields the curator does not model: {unmodelled}")
    tiers = {t: v for t in TIERS if (v := per_mtok(entry.get(LITELLM_FIELD[t]))) is not None}
    if "input" not in tiers or "output" not in tiers:
        return None
    if "cache_write_1h" not in tiers and "cache_write" in tiers and one_hour_is_five_minute:
        tiers["cache_write_1h"] = tiers["cache_write"]
    return Row(harness, model, tiers, long_context_of(name, entry, one_hour_is_five_minute))


# -- records --------------------------------------------------------------------------


def open_record(directory: Path) -> Path | None:
    """The one record with no ``effective_to``, or None when there are no records yet."""
    records = sorted(directory.glob("prices-*.toml"))
    open_ = [p for p in records if "effective_to" not in tomllib.loads(p.read_text(encoding="utf-8"))]
    if not records:
        return None
    if len(open_) != 1:
        raise FeedError(f"expected exactly one open record in {directory}, found {[p.name for p in open_]}")
    return open_[0]


def header_comments(text: str) -> dict[tuple[str, str], list[str]]:
    """The comment lines directly under each ``[harness."model"]`` header."""
    out: dict[tuple[str, str], list[str]] = {}
    current: tuple[str, str] | None = None
    for line in text.splitlines():
        if m := re.fullmatch(r'\[(\w+)\."([^"]+)"\]', line.strip()):
            current = (m.group(1), m.group(2))
            out[current] = []
        elif current and line.startswith("#"):
            out[current].append(line)
        elif line.strip():
            current = None
    return out


def read_rows(path: Path) -> dict[tuple[str, str], Row]:
    """The rows of a record, each with its long-context tier and the comments under its header."""
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    comments = header_comments(path.read_text(encoding="utf-8"))
    rows = {}
    for harness, models in raw.items():
        if not isinstance(models, dict):
            continue
        for model, stated in models.items():
            tiers = {k: float(v) for k, v in stated.items() if k != LONG_CONTEXT}
            long = stated.get(LONG_CONTEXT)
            long_context = {k: float(v) for k, v in long.items()} if isinstance(long, dict) else None
            rows[(harness, model)] = Row(harness, model, tiers, long_context, comments.get((harness, model), []))
    return rows


def money(value: float | None) -> str:
    if value is None:
        return "–"
    text = f"{value:.4f}".rstrip("0")
    whole, _, frac = text.partition(".")
    return f"{whole}.{frac.ljust(2, '0')}"


def shown(name: str, value: float | None) -> str:
    """A rate as money, but a threshold as the whole token count it is."""
    return str(int(value)) if value is not None and name.endswith(THRESHOLD) else money(value)


#: What every record says about itself before its provenance lines.
RECORD_PREAMBLE = (
    "# One dated price record (ADR 0050, ADR 0051). Rates are USD per million tokens, the unit",
    "# every provider publishes; the arithmetic divides by 1e6 once, per tier, at pricing time.",
    "#",
    "# The interval is half-open: a run whose stamp falls on or after `effective_from` and",
    "# before `effective_to` prices from this file. `effective_to` is omitted on the one file",
    "# still in effect. A run date no file covers stops the sweep; it never prices as zero (ADR 0007).",
    "#",
    "# A `long_context` table is the tier a call is billed at, in full, once its prompt (input",
    "# plus cached input) exceeds `above_prompt_tokens`. Each call is priced on its own prompt.",
    "#",
)


def render(rows: Iterable[Row], effective_from: date, provenance: Sequence[str], harness_order: Sequence[str]) -> str:
    """A record in the bundled format: the preamble, its provenance, the date, then rows by harness."""
    lines = [*RECORD_PREAMBLE, *provenance, f"effective_from = {effective_from.isoformat()}"]
    order = {h: i for i, h in enumerate(harness_order)}
    for row in sorted(rows, key=lambda r: (order.get(r.harness, len(order)), r.model)):
        lines += ["", f'[{row.harness}."{row.model}"]', *row.comments]
        lines += [f"{t:<14} = {money(row.tiers[t])}" for t in TIERS if t in row.tiers]
        if row.long_context:
            lc = row.long_context
            lines += ["", f'[{row.harness}."{row.model}".{LONG_CONTEXT}]', f"{THRESHOLD} = {int(lc[THRESHOLD])}"]
            lines += [f"{t:<14} = {money(lc[t])}" for t in TIERS if t in lc]
    return "\n".join(lines) + "\n"


def close(text: str, on: date) -> str:
    """The open record's text with ``effective_to`` set: the one edit an open record ever takes."""
    # Read the parsed record, not the text: every header comment mentions `effective_to`.
    if "effective_to" in tomllib.loads(text):
        raise FeedError("the record to close already has an effective_to")
    note = f"# Closed when prices-{on:%Y%m%d}.toml opened; this record is never edited again."
    closed, n = re.subn(
        r"^(effective_from = \d{4}-\d{2}-\d{2})$",
        rf"\1\n{note}\neffective_to = {on.isoformat()}",
        text,
        count=1,
        flags=re.M,
    )
    if n != 1:
        raise FeedError("no effective_from line to close after")
    return closed


# -- live pricing ---------------------------------------------------------------------


def live_rows(missing: Iterable[tuple[str, str]], feed: dict[str, Any], feeds: Sequence[Feed]) -> list[Row]:
    """The feed's first-party rows for each missing ``(harness, model)``, where it has one.

    A model is matched by its exact id and its harness's ``litellm_provider``: a host's own
    spelling of the model is never a first-party rate (ADR 0051). A model the feed does not
    price is simply absent from the result, and the caller's price check refuses it by name.
    """
    by_harness = {f.harness: f for f in feeds}
    rows = []
    for harness, model in missing:
        source = by_harness.get(harness)
        entry = feed.get(model)
        if source is None or not isinstance(entry, dict) or entry.get("litellm_provider") != source.provider:
            continue
        row = row_from(harness, model, entry, source.one_hour_is_five_minute)
        if row is not None:
            rows.append(row)
    return rows


def write_live_record(
    directory: Path, rows: Sequence[Row], on: date, source: str, harness_order: Sequence[str]
) -> Path:
    """Add ``rows`` to the open record under ``directory``, effective from ``on`` (ADR 0050, ADR 0060).

    The open record from ``on`` gains the rows in place. An open record from an earlier day is
    closed on ``on`` and its rows are carried into the new one, exactly as the curator closes a
    bundled record, so every day a run was stamped with still resolves to the rates it had.
    """
    directory.mkdir(parents=True, exist_ok=True)
    current = open_record(directory)
    carried: dict[tuple[str, str], Row] = read_rows(current) if current else {}
    target = directory / f"prices-{on:%Y%m%d}.toml"
    if current is not None and current != target:
        current.write_text(close(current.read_text(encoding="utf-8"), on), encoding="utf-8")
    merged = {**carried, **{(r.harness, r.model): r for r in rows}}
    provenance = (
        "# Priced live by pytest-xharness-eval at collection, for catalogued models no bundled",
        f"# record covered (ADR 0060). From {source}.",
    )
    target.write_text(render(merged.values(), on, provenance, harness_order), encoding="utf-8")
    return target
