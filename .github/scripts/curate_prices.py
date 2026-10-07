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
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

# Our Libraries
# The feed conversion and the record format are the package's, shared with live pricing
# (ADR 0060), so the two writers cannot disagree on how a feed entry becomes a row.
from pytest_xharness_eval.derive import feed as shared
from pytest_xharness_eval.derive.feed import (  # the constants are re-exported for the curator's own tests
    LITELLM_FIELD,  # noqa: F401
    LONG_CONTEXT,  # noqa: F401
    THRESHOLD,  # noqa: F401
    Row,
    close,
    open_record,
    read_rows,
    shown,
)
from pytest_xharness_eval.derive.feed import FeedError as CurationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PRICES_DIR = PROJECT_ROOT / "src" / "pytest_xharness_eval" / "derive" / "prices"
STAGING = PROJECT_ROOT / "tmp" / "curate-prices"

REPO = "BerriAI/litellm"
FEED_PATH = "model_prices_and_context_window.json"
COMMITS_API = f"https://api.github.com/repos/{REPO}/commits?path={FEED_PATH}&per_page=1"
RAW = "https://raw.githubusercontent.com/{repo}/{ref}/{path}"

KEEP_MARKER = "# curate: keep"


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


def row_from(watch: Watch, key: str, entry: dict) -> Row | None:
    """One feed entry as a row in USD per MTok, by the conversion live pricing uses too (ADR 0060)."""
    return shared.row_from(watch.harness, key, entry, watch.one_hour_is_five_minute)


# -- the open record ------------------------------------------------------------------


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


def render(rows: list[Row], effective_from: date, commit: str, fetched: date) -> str:
    """A bundled record: the shared format, with the curator's own provenance header."""
    provenance = (
        "# Curated by .github/scripts/curate_prices.py from",
        f"# https://github.com/{REPO}/blob/{commit}/{FEED_PATH}",
        f"# (fetched {fetched.isoformat()}). First-party rows only: anthropic under [claude], openai under [codex].",
        "# OpenAI publishes no 1-hour cache-write tier, so each [codex] cache_write_1h repeats its",
        "# cache_write: an assumption, stated, never a zero.",
        "# A row with a comment line starting `# curate: keep` is a local override never re-priced.",
    )
    return shared.render(rows, effective_from, provenance, [w.harness for w in WATCHES])


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
    from pytest_xharness_eval.derive.catalogue import load_catalogue
    from pytest_xharness_eval.model import matrix

    table = pricing.PriceTable(tuple(pricing.load_records(staged)))
    table.validate_matrix(matrix.catalogued(load_catalogue()), on)


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
    parser.add_argument(
        "--when-catalogue-unpriced",
        action="store_true",
        help="curate only when a model in derive/prices/models.toml has no bundled price today; "
        "otherwise exit at once without touching the network (what `make test` runs, ADR 0060)",
    )
    return parser.parse_args(argv)


def catalogue_unpriced(on: date) -> list[str]:
    """Every catalogued model the bundled records leave unpriced on ``on``: the trigger for a new snapshot."""
    # Our Libraries
    from pytest_xharness_eval.derive import pricing
    from pytest_xharness_eval.derive.catalogue import load_catalogue
    from pytest_xharness_eval.model import matrix

    table = pricing.PriceTable(tuple(pricing.load_records(PRICES_DIR)))
    return [f"{h}/{m}" for h, m in table.unpriced(matrix.catalogued(load_catalogue()), on)]


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
    if args.when_catalogue_unpriced:
        missing = catalogue_unpriced(args.date)
        if not missing:
            print("every catalogued model is priced; nothing to curate")
            return 0
        print(f"catalogued but unpriced, curating a new snapshot: {missing}")
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
