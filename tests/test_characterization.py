"""Characterization tests: the pinned, observable output of the normalise -> price ->
coverage pipeline for both harness dialects.

These do not assert what the pipeline *should* do; they pin what it *does*, so a
structural move (extracting a Harness/SessionLog hierarchy, a settings layer or a
shared pipeline) can be proved behaviour-preserving rather than merely green. A
golden that changes is a decision, not a diff to wave through: classify it as a
pinned bug, pinned noise, or a genuine behaviour change before updating it.

Regenerate deliberately with ``XHARNESS_UPDATE_GOLDEN=1 uv run pytest tests/test_characterization.py``.
"""

from __future__ import annotations

# Standard Library
import json
import os
from pathlib import Path
from typing import Any

# Third Party
import pytest
from characterization_fixtures import (
    PRICE_ROWS,
    SKILL,
    claude_capture,
    codex_capture,
    skill_tree,
)

# Our Libraries
from pytest_xharness_eval import RunResult, harness, normalise, pricing, records, replay, skillcov

GOLDEN_DIR = Path(__file__).parent / "golden"


def _table() -> dict[str, pricing.Rates]:
    return pricing.load_table(rows=PRICE_ROWS)


def _case(name: str) -> dict[str, Any]:
    return {
        "suite": f"skills/{SKILL}/evals/eval_{name}.py",
        "name": f"eval_{name}",
        "skill": SKILL,
        "fixture": "seed",
        "task": "grade the skill",
        "prompt": f"/{SKILL} grade the skill",
    }


def _finish(result: RunResult, files: list[dict[str, Any]], name: str) -> RunResult:
    """The post-run steps plugin.EvalItem._run_live applies, in its order."""
    pricing.price(result, _table())
    result.skill_coverage = skillcov.annotate(SKILL, files, result)
    result.case = _case(name)
    return result


# Values that move on every run without any behaviour changing: the tmp_path prefix and
# the wall-clock stamp ``pricing.rates_record`` writes. Pinning them would pin noise, so
# they are normalised out rather than asserted (they are covered by their own unit tests).
NOISE_KEYS = ("applied_at",)


def _scrub(value: Any, tmp_path: Path) -> Any:
    """Normalise the machine- and clock-dependent values out of a payload."""
    root = str(tmp_path)
    if isinstance(value, str):
        return value.replace(root, "<tmp>")
    if isinstance(value, dict):
        return {k: ("<stamp>" if k in NOISE_KEYS else _scrub(v, tmp_path)) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v, tmp_path) for v in value]
    return value


def _assert_golden(name: str, payload: Any) -> None:
    path = GOLDEN_DIR / f"{name}.json"
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if os.environ.get("XHARNESS_UPDATE_GOLDEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return
    assert path.is_file(), f"missing golden {path}; regenerate with XHARNESS_UPDATE_GOLDEN=1"
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert json.loads(text) == expected, (
        f"{name} drifted from its pinned output. A structural change must not move this file: "
        "classify the change (pinned bug / pinned noise / genuine behaviour change) before regenerating."
    )


def _built(tmp_path: Path, harness_name: str) -> tuple[RunResult, Path, list[dict[str, Any]]]:
    """Build one capture and fold it exactly as a live run would."""
    skill_dir = skill_tree(tmp_path / "skills")
    files = skillcov.catalog(skill_dir)
    workspace = tmp_path / "ws"
    workspace.mkdir(exist_ok=True)
    session_dir = tmp_path / "results" / harness_name / "sid"
    if harness_name == "claude":
        log, envelope = claude_capture(session_dir)
        result = harness.ClaudeSessionLog(log, envelope).to_result(workspace, ["out.md"])
    else:
        log = codex_capture(session_dir)
        result = harness.CodexSessionLog(log, 0).to_result(workspace, ["out.md"])
    return _finish(result, files, harness_name), session_dir, files


# -- the pinned pipeline output --------------------------------------------------------


@pytest.mark.parametrize("harness_name", ["claude", "codex"])
def test_pipeline_output_is_pinned(tmp_path: Path, harness_name: str) -> None:
    """The whole serialised RunResult for a rich capture: ledger, usage, pricing, coverage, subagents."""
    result, _session_dir, _files = _built(tmp_path, harness_name)
    _assert_golden(f"{harness_name}_result", _scrub(result.to_dict(), tmp_path))


@pytest.mark.parametrize("harness_name", ["claude", "codex"])
def test_replay_reproduces_the_live_result(tmp_path: Path, harness_name: str) -> None:
    """Replay re-derives the same result from the captured session dir alone.

    This is the invariant that the Claude envelope reconstruction in ``replay`` exists to
    hold: a captured log plus its stored ``result.json`` must fold back to what the live
    run produced. ``session_log`` and each subagent's ``log`` are the paths the capture
    lives at and legitimately differ between the two paths; everything else must match.
    """
    live, session_dir, files = _built(tmp_path, harness_name)
    live.write(session_dir / "result.json")

    rebuilt = replay.rebuild_result(session_dir, _table(), files, SKILL)

    def comparable(d: dict[str, Any]) -> dict[str, Any]:
        out = {k: v for k, v in d.items() if k != "session_log"}
        out["subagents"] = [{k: v for k, v in s.items() if k != "log"} for s in out.get("subagents", [])]
        return out

    assert comparable(_scrub(rebuilt.to_dict(), tmp_path)) == comparable(_scrub(live.to_dict(), tmp_path))


# -- the record catalogue ---------------------------------------------------------------


def test_record_classification_is_pinned(tmp_path: Path) -> None:
    """Every record of both captures, classified and categorised: the dispatch table itself."""
    session = tmp_path / "s"
    claude_log, _ = claude_capture(session / "claude")
    codex_log = codex_capture(session / "codex")
    pinned: dict[str, Any] = {}
    for name, log in (("claude", claude_log), ("codex", codex_log)):
        agent = harness.get(name)
        rows = normalise.read_jsonl(log)
        pinned[name] = {
            "census": agent.census(rows),
            "categories": {k: records.category_of(k) for k in agent.census(rows)},
        }
    _assert_golden("record_kinds", pinned)


def test_unknown_harness_is_loud_not_silently_codex() -> None:
    """The behaviour this refactoring set out to change, pinned in its new form.

    Classification used to dispatch ``claude`` explicitly and fall through to the Codex
    classifier for everything else, so an unregistered harness was silently read as a
    Codex record. It now goes through the registry and raises (ADR 0034).
    """
    with pytest.raises(harness.UnknownHarness, match="unknown harness 'gemini'"):
        harness.get("gemini")
