"""Rebuild captured results from their session logs without re-running anything (ADR 0023).

A captured cell is its session log plus the CLI's envelope, both kept verbatim.
Everything else in a ``.result.json`` (the ledger, usage, pricing, record census,
skill coverage) is derived, so it can be derived again after the plugin changes:

    uv run -m pytest_xharness_eval.replay skills/<skill>/evals/captured

rewrites every ``.result.json`` under the directory from its log, re-prices it
with the current price tables, re-annotates skill coverage against the skill's
current tree and ignore rules, rewrites the matching ``history.jsonl`` lines
(verdict, timestamps and wall clock are kept; metrics are recomputed), and
regenerates ``index.json`` and ``report.html``. No CLI is invoked and nothing
is spent.
"""

from __future__ import annotations

# Standard Library
import argparse
import configparser
import hashlib
import importlib.util
import json
import logging
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Our Libraries
from pytest_xharness_eval import history, normalise, pricing, report, skillcov
from pytest_xharness_eval.case import EvalCase

if TYPE_CHECKING:
    # Standard Library
    from types import ModuleType

    # Our Libraries
    from pytest_xharness_eval.runresult import RunResult

log = logging.getLogger(__name__)


def skill_dir_of(captured: Path) -> Path:
    """``<skills root>/<skill>/evals/captured`` -> ``<skills root>/<skill>``."""
    return captured.resolve().parent.parent


# pytest's own config files, in the order it consults them (rootdir discovery).
_CONFIG_FILES = ("pytest.ini", ".pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg")


def ignore_lines_of(captured: Path, key: str = "xharness_skill_ignore") -> list[str]:
    """The project's ``xharness_skill_ignore`` lines, read from its pytest config file.

    Replay runs outside a pytest session, so it resolves the key the way pytest
    would: the first ancestor of ``captured`` holding a ``pytest.ini``,
    ``pyproject.toml`` (``[tool.pytest.ini_options]``), ``tox.ini`` (``[pytest]``)
    or ``setup.cfg`` (``[tool:pytest]``) wins. A missing file or key is no lines, so
    a replay and a live sweep agree on what is decision surface.
    """
    for directory in (captured.resolve(), *captured.resolve().parents):
        for name in _CONFIG_FILES:
            path = directory / name
            if not path.is_file():
                continue
            if name == "pyproject.toml":
                section = tomllib.loads(path.read_text(encoding="utf-8")).get("tool", {}).get("pytest", {})
                options = section.get("ini_options")
                if options is None:
                    continue  # a pyproject.toml without pytest options is not pytest's config file
                value = options.get(key, [])
                return [str(v) for v in value] if isinstance(value, list) else str(value).splitlines()
            parser = configparser.ConfigParser(interpolation=None)
            parser.read(path, encoding="utf-8")
            section_name = "tool:pytest" if name == "setup.cfg" else "pytest"
            if not parser.has_section(section_name):
                continue
            return [line.strip() for line in parser.get(section_name, key, fallback="").splitlines() if line.strip()]
    return []


def rebuild_result(
    result_path: Path, table: dict[str, pricing.Rates], files: list[dict[str, Any]], skill: str
) -> RunResult:
    """Re-derive one result from its captured log and stored envelope; returns the new RunResult."""
    old = json.loads(result_path.read_text(encoding="utf-8"))
    stem = result_path.name.removesuffix(".result.json")
    log_path = result_path.with_name(f"{stem}.jsonl")
    if not log_path.is_file():
        raise FileNotFoundError(f"no captured session log beside {result_path.name}: {log_path.name}")
    workspace = Path(old.get("workspace") or "")
    files_written = list(old.get("files_written") or [])
    if old.get("harness") == "claude":
        envelope = dict(old.get("envelope") or {})
        envelope.setdefault("session_id", old.get("session_id"))
        envelope.setdefault("total_cost_usd", old.get("harness_reported_cost_usd"))
        envelope.setdefault("duration_ms", old.get("duration_ms"))
        envelope["result"] = old.get("final_text") or ""
        result = normalise.from_claude(log_path, envelope, workspace, files_written)
    else:
        result = normalise.from_codex(log_path, int(old.get("exit_code") or 0), workspace, files_written)
    pricing.price(result, table)
    result.skill_coverage = skillcov.annotate(skill, files, result)
    # The case that produced the run is not in the log: carry it forward, or derive it from the suite
    # that defines a case named after the captured directory (ADR 0025).
    result.case = dict(old.get("case") or {}) or case_meta(result_path.parent.parent, result_path.parent.name)
    return result


def case_meta(captured: Path, name: str) -> dict[str, Any]:
    """``{suite, name, skill, fixture, prompt}`` for the ``@evalcase`` called ``name`` in ``<evals>/eval_*.py``.

    ``captured`` is ``<skill>/evals/captured``; the suites sit beside it. An empty
    mapping when no suite defines the case (the file may have been renamed).
    """
    evals_dir = captured.resolve().parent
    for suite_path in sorted(evals_dir.glob("eval_*.py")):
        try:
            module = _load_suite(suite_path)
        except Exception as exc:  # noqa: BLE001 - a broken suite must not block replaying the others
            log.warning("could not import %s to recover case metadata: %s", suite_path.name, exc)
            continue
        for value in vars(module).values():
            if isinstance(value, EvalCase) and value.name == name:
                try:
                    suite = str(suite_path.relative_to(Path.cwd()))
                except ValueError:
                    suite = str(suite_path)
                return {
                    "suite": suite,
                    "name": name,
                    "skill": value.skill,
                    "fixture": value.fixture,
                    "prompt": value.prompt,
                }
    return {}


def _load_suite(path: Path) -> ModuleType:
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:8]
    spec = importlib.util.spec_from_file_location(f"_xharness_replay_{path.stem}_{digest}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load eval module {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rebuild(
    captured: Path,
    prices: Path | None = None,
    ignore: list[str] | None = None,
    design_tokens: Path | None = None,
    inline: bool = False,
) -> list[Path]:
    """Rebuild every result under ``captured``; rewrite history lines and the report. Returns the rewritten results.

    ``ignore`` lines are added to the project's ``xharness_skill_ignore`` lines (see
    ``ignore_lines_of``), in the same ``<pattern>`` or ``<skill>: <pattern>`` form.
    """
    table = pricing.load_table(overrides=prices)
    skill_dir = skill_dir_of(captured)
    ignore_lines = ignore_lines_of(captured) + list(ignore or [])
    files = skillcov.catalog(skill_dir, ignore=ignore_lines) if skill_dir.is_dir() else []
    skill = skill_dir.name
    history_path = captured / "history.jsonl"
    lines: list[dict[str, Any]] = []
    if history_path.is_file():
        for raw in history_path.read_text(encoding="utf-8").splitlines():
            if raw.strip():
                lines.append(json.loads(raw))
    by_session = {str(rec.get("session_id")): rec for rec in lines}

    rewritten: list[Path] = []
    for result_path in sorted(captured.glob("*/*.result.json")):
        result = rebuild_result(result_path, table, files, skill)
        result.write(result_path)
        rewritten.append(result_path)
        old = by_session.get(result.session_id)
        if old is not None:
            fresh = history.metrics_of(
                result,
                node=str(old.get("node") or ""),
                verdict=str(old.get("verdict") or ""),
                wall_ms=int(old.get("wall_ms") or 0),
                started_at=str(old.get("at") or ""),
            )
            fresh["captured"] = old.get("captured") or str(captured)
            old.clear()
            old.update(fresh)
        log.info("rebuilt %s: %d turns, %s", result_path.name, result.turns, result.skill_coverage.get("summary"))

    if lines:
        history_path.write_text("".join(json.dumps(rec, sort_keys=True) + "\n" for rec in lines), encoding="utf-8")
    page = report.write(captured, design_tokens=design_tokens, inline=inline)
    log.info("report: %s%s", page, " (inline)" if inline else "")
    return rewritten


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rebuild captured eval results from their session logs; no CLI runs, nothing is spent."
    )
    parser.add_argument("captured", type=Path, help="a <skill>/evals/captured directory")
    parser.add_argument(
        "--prices",
        type=Path,
        default=Path("prices.toml"),
        help="project prices.toml layered over the bundled table (default: ./prices.toml)",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="PATTERN",
        help=(
            "extra xharness_skill_ignore line, '<pattern>' or '<skill>: <pattern>' (repeatable; "
            "the project's pytest config lines apply as well)"
        ),
    )
    parser.add_argument(
        "--design-tokens", type=Path, default=None, metavar="FILE", help="design tokens JSON to theme report.html"
    )
    parser.add_argument("--inline", action="store_true", help="embed every result, log and the tokens into report.html")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
    if not args.captured.is_dir():
        raise SystemExit(f"not a directory: {args.captured}")
    rebuilt = rebuild(
        args.captured,
        prices=args.prices if args.prices.is_file() else None,
        ignore=args.ignore,
        design_tokens=args.design_tokens,
        inline=args.inline,
    )
    log.info("rebuilt %d result(s) under %s", len(rebuilt), args.captured)


if __name__ == "__main__":
    main()
