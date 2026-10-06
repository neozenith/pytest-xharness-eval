#!/usr/bin/env python
"""Curate a dated price record from LiteLLM's feed (ADR 0006's upstream seed, ADR 0050, ADR 0051).

    make prices                       # today, UTC; writes only on a change
    make prices ARGS="--dry-run"      # stage and report; write nothing into the package
    uv run .github/scripts/curate_prices.py --date 2026-10-01

It fetches ``model_prices_and_context_window.json`` from BerriAI/litellm at a pinned commit.
It keeps only the first-party rows of the watched families and models every published rate
on them, including a long-context tier. It stages the new record under ``tmp/curate-prices/``.
The staged record set must load through the plugin's own ``pricing.load_records`` and still
price the default matrix before anything is written. Only then is the open record closed on
the new date, and the new record written beside it into ``src/.../derive/prices/``. A closed
record is never edited again (ADR 0050). With no record at all, the first one is bootstrapped.

Run it with ``uv run`` from the repository root, inside the project environment. It imports
``pytest_xharness_eval`` to validate what it writes, so it carries no PEP 723 block.

The rules, and why each exists (ADR 0051 records the grammars and the evidence):

* **First-party rows only.** The harness session logs report first-party IDs, so those are
  the IDs a price row is keyed by. Hosts price their own spellings differently (regional
  surcharges, batch rates, ``-pro`` tiers), and no harness ever logs them.
* **Scope is a boundary, not a roster.** A watch owns a shape of ID above a generation
  floor, so a new release (``gpt-7``, a new Claude tier) is curated without an edit here
  (ADR 0052). Each owned ID is parsed with its vendor's grammar. An owned ID that fits no
  grammar stops the run: its shape is new, and guessing would price it by accident (ADR 0007).
* **Every published rate is modelled.** The five base tiers and any ``_above_<N>k_tokens``
  long-context tier are written as data. A cost field the curator does not model and does
  not deliberately ignore stops the run, so a new pricing dimension cannot vanish silently.
* **Local overrides win.** A row with a comment line starting ``# curate: keep`` keeps our
  rates (ADR 0006). The rest of that line is the place to say why.
* **Nothing is dropped silently.** A row the feed no longer has is carried forward with a
  note. A model cannot lose its price because LiteLLM dropped it.
* **No-op when nothing changed.** A new record is written only if a row was added,
  re-priced, or carried forward, unless ``--always`` is passed.
"""

from __future__ import annotations

# Standard Library
import argparse
import json
import re
import shutil
import sys
import tomllib
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PRICES_DIR = PROJECT_ROOT / "src" / "pytest_xharness_eval" / "derive" / "prices"
STAGING = PROJECT_ROOT / "tmp" / "curate-prices"

REPO = "BerriAI/litellm"
FEED_PATH = "model_prices_and_context_window.json"
COMMITS_API = f"https://api.github.com/repos/{REPO}/commits?path={FEED_PATH}&per_page=1"
RAW = "https://raw.githubusercontent.com/{repo}/{ref}/{path}"

KEEP_MARKER = "# curate: keep"
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


@dataclass(frozen=True)
class Watch:
    """One harness's slice of the feed: which provider's rows, bounded by shape and generation floor."""

    harness: str
    provider: str
    shape: re.Pattern[str]  # the ids this watch owns; an owned id the grammar cannot parse stops the run
    grammar: re.Pattern[str]  # names the ``family`` of an owned id
    floor: tuple[int, ...] | None  # lowest ``generation`` owned (the shape's named group); None: no floor
    one_hour_is_five_minute: bool  # the provider publishes no 1h cache-write tier

    def owns(self, key: str) -> bool:
        """Whether ``key`` is this watch's to parse: in shape and at or above the floor, parsable or not."""
        m = self.shape.fullmatch(key)
        if m is None:
            return False
        return self.floor is None or generation(m.group("generation")) >= self.floor

    def family_of(self, key: str) -> str | None:
        m = self.grammar.fullmatch(key)
        return m.group("family") if m else None


def generation(text: str) -> tuple[int, ...]:
    """A dotted generation as a comparable tuple: "5.6" -> (5, 6), "6" -> (6,), "5.10" -> (5, 10)."""
    return tuple(int(part) for part in text.split("."))


# The watch-list, as boundaries rather than rosters (ADR 0052): a release that fits a grammar
# and clears its floor is curated without an edit here, and one whose shape is new stops the
# run. Moving a boundary is a reviewed edit; ADR 0051 records the grammars.
WATCHES = (
    Watch(
        harness="claude",
        provider="anthropic",
        shape=re.compile(r"claude-.*"),
        # A tier is any word in the tier position, so a new tier needs no edit here.
        grammar=re.compile(r"(?P<family>claude-[a-z]+)-(?:\d+(?:-\d)?(?:-20\d{6})?|preview)"),
        floor=None,
        one_hour_is_five_minute=False,
    ),
    Watch(
        harness="codex",
        provider="openai",
        # A number after "gpt-" is a generation; a word is a sub-line (gpt-image, gpt-realtime),
        # out of scope by shape. The lookahead stops "gpt-4o" reading as generation 4.
        shape=re.compile(r"gpt-(?P<generation>\d+(?:\.\d+)?)(?![\d.]).*"),
        grammar=re.compile(r"(?P<family>gpt-\d+(?:\.\d+)?)(?:-[a-z]+)?"),
        floor=(5, 6),  # gpt-5.6 and every later generation: gpt-6, gpt-7, gpt-7.1, ...
        one_hour_is_five_minute=True,
    ),
)


class CurationError(RuntimeError):
    """A condition the curator refuses to guess past."""


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


def fetch_feed(ref: str | None) -> tuple[dict, str]:
    """The feed at ``ref``, or at the last commit that touched it; returns (feed, commit)."""
    if ref is None:
        with urllib.request.urlopen(_request(COMMITS_API), timeout=30) as resp:
            ref = json.load(resp)[0]["sha"]
    url = RAW.format(repo=REPO, ref=ref, path=FEED_PATH)
    with urllib.request.urlopen(_request(url), timeout=60) as resp:
        return json.load(resp), str(ref)


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": "pytest-xharness-eval-curate-prices"})


def per_mtok(value: object) -> float | None:
    """A per-token rate as USD per MTok, rounded past float noise (3e-06 -> 3.0)."""
    return round(float(value) * 1_000_000, 6) if isinstance(value, int | float) else None


def select(feed: dict) -> tuple[list[Row], list[str], list[str]]:
    """The watched first-party rows; plus the ids skipped as unpriced, and those no grammar fits."""
    rows: list[Row] = []
    unpriced: list[str] = []
    unrecognised: list[str] = []
    for key, entry in sorted(feed.items()):
        if not isinstance(entry, dict):
            continue
        for watch in WATCHES:
            if entry.get("litellm_provider") != watch.provider or not watch.owns(key):
                continue
            if watch.family_of(key) is None:
                unrecognised.append(f"{watch.harness}/{key}")
                continue
            row = row_from(watch, key, entry)
            if row is None:
                unpriced.append(f"{watch.harness}/{key}")
            else:
                rows.append(row)
    return rows, unpriced, unrecognised


def unmodelled_fields(entry: dict) -> list[str]:
    """Cost fields on ``entry`` the curator neither models nor deliberately ignores."""
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


def long_context_of(watch: Watch, key: str, entry: dict) -> dict[str, float] | None:
    """The long-context tier from ``*_above_<N>k_tokens`` fields: one threshold, all tiers at it."""
    found: dict[str, float] = {}
    thresholds = set()
    by_field = {v: k for k, v in LITELLM_FIELD.items()}
    for name, value in entry.items():
        m = LONG_FIELD.fullmatch(name)
        if m and (rate := per_mtok(value)) is not None:
            thresholds.add(int(m.group("k")) * 1000)  # LiteLLM reads "272k" as 272,000
            found[by_field[m.group("field")]] = rate
    if not found:
        return None
    if len(thresholds) != 1:
        raise CurationError(
            f"{watch.harness}/{key}: long-context fields disagree on the threshold: {sorted(thresholds)}"
        )
    if "input" not in found or "output" not in found:
        raise CurationError(f"{watch.harness}/{key}: a long-context tier needs input and output rates, got {found}")
    if "cache_write_1h" not in found and "cache_write" in found and watch.one_hour_is_five_minute:
        found["cache_write_1h"] = found["cache_write"]
    return {THRESHOLD: float(thresholds.pop()), **{t: found[t] for t in TIERS if t in found}}


def row_from(watch: Watch, key: str, entry: dict) -> Row | None:
    """One feed entry as a row in USD per MTok, or None when it has no per-token input and output rate."""
    unmodelled = unmodelled_fields(entry)
    if unmodelled:
        raise CurationError(f"{watch.harness}/{key}: cost fields the curator does not model: {unmodelled}")
    tiers = {t: v for t in TIERS if (v := per_mtok(entry.get(LITELLM_FIELD[t]))) is not None}
    if "input" not in tiers or "output" not in tiers:
        return None
    if "cache_write_1h" not in tiers and "cache_write" in tiers and watch.one_hour_is_five_minute:
        tiers["cache_write_1h"] = tiers["cache_write"]
    return Row(watch.harness, key, tiers, long_context_of(watch, key, entry))


# -- the open record ------------------------------------------------------------------


def open_record(directory: Path) -> Path | None:
    """The one record with no ``effective_to``, or None when there are no records yet."""
    records = sorted(directory.glob("prices-*.toml"))
    open_ = [p for p in records if "effective_to" not in tomllib.loads(p.read_text())]
    if not records:
        return None
    if len(open_) != 1:
        raise CurationError(f"expected exactly one open record in {directory}, found {[p.name for p in open_]}")
    return open_[0]


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


def is_kept(row: Row) -> bool:
    return any(c.startswith(KEEP_MARKER) for c in row.comments)


def merge(new: list[Row], old: dict[tuple[str, str], Row]) -> tuple[list[Row], dict[str, list[str]]]:
    """The next record's rows, with overrides kept and vanished rows carried; plus a change report."""
    report: dict[str, list[str]] = {"added": [], "repriced": [], "kept": [], "carried": [], "unchanged": []}
    merged: list[Row] = []
    seen = set()
    for row in new:
        key = (row.harness, row.model)
        seen.add(key)
        prior = old.get(key)
        name = f"{row.harness}/{row.model}"
        if prior is None:
            report["added"].append(name)
            merged.append(row)
        elif is_kept(prior):
            report["kept"].append(name)
            merged.append(prior)
        else:
            before, after = prior.rates(), row.rates()
            diffs = [
                f"{t} {shown(t, before.get(t))}->{shown(t, after.get(t))}"
                for t in sorted(before.keys() | after.keys())
                if before.get(t) != after.get(t)
            ]
            report["repriced" if diffs else "unchanged"].append(name + (f" ({', '.join(diffs)})" if diffs else ""))
            merged.append(Row(row.harness, row.model, row.tiers, row.long_context, prior.comments))
    for key, prior in old.items():
        if key not in seen:
            report["carried"].append(f"{key[0]}/{key[1]}")
            note = "# Carried forward: absent from the LiteLLM feed at this curation."
            merged.append(Row(prior.harness, prior.model, prior.tiers, prior.long_context, [*prior.comments, note]))
    return merged, report


def changed(report: dict[str, list[str]]) -> bool:
    return bool(report["added"] or report["repriced"] or report["carried"])


# -- rendering ------------------------------------------------------------------------


def money(value: float | None) -> str:
    if value is None:
        return "–"
    text = f"{value:.4f}".rstrip("0")
    whole, _, frac = text.partition(".")
    return f"{whole}.{frac.ljust(2, '0')}"


def shown(name: str, value: float | None) -> str:
    """A rate as money, but a threshold as the whole token count it is."""
    return str(int(value)) if value is not None and name.endswith(THRESHOLD) else money(value)


def render(rows: list[Row], effective_from: date, commit: str, fetched: date) -> str:
    """A record in the bundled format: a provenance header, the date, then rows by harness."""
    lines = [
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
        "# Curated by .github/scripts/curate_prices.py from",
        f"# https://github.com/{REPO}/blob/{commit}/{FEED_PATH}",
        f"# (fetched {fetched.isoformat()}). First-party rows only: anthropic under [claude], openai under [codex].",
        "# OpenAI publishes no 1-hour cache-write tier, so each [codex] cache_write_1h repeats its",
        "# cache_write: an assumption, stated, never a zero.",
        "# A row with a comment line starting `# curate: keep` is a local override never re-priced.",
        f"effective_from = {effective_from.isoformat()}",
    ]
    order = {w.harness: i for i, w in enumerate(WATCHES)}
    for row in sorted(rows, key=lambda r: (order.get(r.harness, 99), r.model)):
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
        raise CurationError("the record to close already has an effective_to")
    note = f"# Closed when prices-{on:%Y%m%d}.toml opened; this record is never edited again."
    closed, n = re.subn(
        r"^(effective_from = \d{4}-\d{2}-\d{2})$",
        rf"\1\n{note}\neffective_to = {on.isoformat()}",
        text,
        count=1,
        flags=re.M,
    )
    if n != 1:
        raise CurationError("no effective_from line to close after")
    return closed


# -- validation and the run -----------------------------------------------------------


def stage(directory: Path, closes: tuple[Path, str] | None, new_name: str, new_text: str) -> Path:
    """Copy every record into a staging dir, then apply the close (if any) and the new record there."""
    target = STAGING / new_name.removesuffix(".toml")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for p in directory.glob("prices-*.toml"):
        shutil.copy2(p, target / p.name)
    if closes is not None:
        (target / closes[0].name).write_text(closes[1], encoding="utf-8")
    (target / new_name).write_text(new_text, encoding="utf-8")
    return target


def validate(staged: Path, on: date) -> None:
    """The staged set must load exactly as the plugin loads it, and price every catalogued model (ADR 0057)."""
    # Our Libraries
    from pytest_xharness_eval.derive import pricing
    from pytest_xharness_eval.model import matrix, registry

    table = pricing.PriceTable(tuple(pricing.load_records(staged)))
    table.validate_matrix(matrix.catalogued(registry.catalogue()), on)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Curate a dated price record from LiteLLM's feed.")
    parser.add_argument(
        "--date", type=date.fromisoformat, default=datetime.now(UTC).date(), help="effective_from (default: today, UTC)"
    )
    parser.add_argument(
        "--ref",
        help="LiteLLM commit or branch to read (default: the last commit that touched the feed); "
        "with --feed, only a provenance label",
    )
    parser.add_argument("--feed", type=Path, help="read a local copy of the feed instead of fetching")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="stage and report under tmp/curate-prices; write nothing into the package",
    )
    parser.add_argument("--always", action="store_true", help="write a record even when nothing changed")
    return parser.parse_args(argv)


def report_lines(report: dict[str, list[str]], unpriced: list[str]) -> list[str]:
    lines = []
    for kind, items in report.items():
        lines.append(f"{kind:>9}: {len(items)}")
        if kind != "unchanged":
            lines += [f"           {i}" for i in items]
    lines.append(f" unpriced: {len(unpriced)} skipped")
    lines += [f"           {i}" for i in unpriced]
    return lines


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.feed:
        feed, commit = json.loads(args.feed.read_text(encoding="utf-8")), args.ref or f"local file {args.feed}"
    else:
        feed, commit = fetch_feed(args.ref)
    new_rows, unpriced, unrecognised = select(feed)
    if unrecognised:
        raise CurationError(
            "first-party ids in a watched family fit no grammar; extend WATCHES rather than guess:\n  "
            + "\n  ".join(unrecognised)
        )
    old_path = open_record(PRICES_DIR)
    old_rows = read_rows(old_path) if old_path else {}
    if old_path is not None:
        opened = date.fromisoformat(str(tomllib.loads(old_path.read_text())["effective_from"]))
        if args.date <= opened:
            raise CurationError(
                f"--date {args.date} must be after the open record's effective_from {opened} ({old_path.name})"
            )
    merged, report = merge(new_rows, old_rows)
    print("\n".join(report_lines(report, unpriced)))
    if not changed(report) and not args.always:
        print(f"nothing changed since {old_path.name if old_path else 'no record'}; nothing written")
        return 0
    new_name = f"prices-{args.date:%Y%m%d}.toml"
    new_text = render(merged, args.date, commit, datetime.now(UTC).date())
    closes = (old_path, close(old_path.read_text(encoding="utf-8"), args.date)) if old_path else None
    staged = stage(PRICES_DIR, closes, new_name, new_text)
    validate(staged, args.date)
    print(f"staged and validated: {staged / new_name}")
    if args.dry_run:
        print("dry run: nothing written into the package")
        return 0
    if closes is not None:
        closes[0].write_text(closes[1], encoding="utf-8")
    PRICES_DIR.mkdir(parents=True, exist_ok=True)
    (PRICES_DIR / new_name).write_text(new_text, encoding="utf-8")
    print(
        ("closed " + closes[0].name + "; " if closes else "bootstrapped the first record; ")
        + f"wrote {PRICES_DIR / new_name}"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CurationError as exc:
        print(f"curate_prices: {exc}", file=sys.stderr)
        sys.exit(1)
