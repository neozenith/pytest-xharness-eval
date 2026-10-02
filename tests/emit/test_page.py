"""``emit.page``: the combine step that writes the report microsite (ADR 0032)."""

# Standard Library
import json
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import (
    Call,
    CaseRef,
    ToolCall,
    Usage,
)
from pytest_xharness_eval.emit import page
from pytest_xharness_eval.model.layout import CacheLayout
from tests.support import _applied_rates, _result


def test_report_indexes_every_captured_result_and_writes_the_page(tmp_path: Path) -> None:
    cache = tmp_path / ".xharness_eval_cache"
    claude_dir = cache / "results" / "demo" / "claude" / "claude-opus-5" / "20260822T010000Z" / "9f5f73a0"
    new = _result("claude-opus-5", Usage(26, 5289, 492_998, 28_154, cache_write_1h_tokens=28_154))
    new.harness, new.session_id, new.turns = "claude", "9f5f73a0", 13
    new.harness_reported_cost_usd, new.estimated_cost_usd = 0.66, 0.55
    new.rates_applied = _applied_rates(model="claude-opus-5")
    new.case = CaseRef(name="eval_demo", skill="demo")
    new.calls = [
        Call(n=1, at="t", usage=Usage(input_tokens=2, cache_read_tokens=22_954), tools=[ToolCall("Bash", "ls")])
    ]
    new.write(claude_dir / "result.json")
    (claude_dir / "log.jsonl").write_text("{}\n", encoding="utf-8")
    (claude_dir / "history.json").write_text(
        json.dumps(
            {
                "session_id": "9f5f73a0",
                "verdict": "pass",
                "at": "2026-08-22T01:00:00+00:00",
                "node": "n",
                "wall_ms": 87_070,
            }
        ),
        encoding="utf-8",
    )
    # A result written before ADR 0019: no calls, no history record, no log, no case meta.
    codex_dir = cache / "results" / "demo" / "codex" / "gpt-5.6-sol" / "20260821T000000Z" / "01a022dc"
    old = _result("gpt-5.6-sol", Usage(100, 10, 0, 0))
    old.harness, old.session_id = "codex", "01a022dc"
    old.write(codex_dir / "result.json")

    report_page = page.write(CacheLayout(cache))
    assert report_page == cache / "report" / "report.html"
    html = report_page.read_text(encoding="utf-8")
    assert "index.json" in html and "window.__XH_DATA__ = " not in html and page.INLINE_MARKER not in html
    report_dir = cache / "report"
    assert "# xharness report glossary" in (report_dir / "XHARNESS-REPORT-GLOSSARY.md").read_text(encoding="utf-8")
    # The bundled design tokens land beside the page so they can be edited in place (ADR 0024).
    tokens = json.loads((report_dir / "report.tokens.json").read_text(encoding="utf-8"))
    assert set(tokens["themes"]) == {"light", "dark"} and tokens["categories"]["prompt"] == "#1d4ed8"
    index = json.loads((report_dir / "index.json").read_text(encoding="utf-8"))
    assert index["captured"] == str(cache)
    # The aggregated history is the combine step's other output (ADR 0032).
    aggregated = [json.loads(raw) for raw in (report_dir / "history.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [rec["session_id"] for rec in aggregated] == ["9f5f73a0"]
    first, second = index["cells"]  # newest first; the one without history sorts last
    assert (first["case"], first["harness"], first["model"], first["session_id"]) == (
        "eval_demo",
        "claude",
        "claude-opus-5",
        "9f5f73a0",
    )
    assert (first["verdict"], first["at"], first["wall_ms"], first["node"]) == (
        "pass",
        "2026-08-22T01:00:00+00:00",
        87_070,
        "n",
    )
    assert (first["result"], first["log"]) == (
        "../results/demo/claude/claude-opus-5/20260822T010000Z/9f5f73a0/result.json",
        "../results/demo/claude/claude-opus-5/20260822T010000Z/9f5f73a0/log.jsonl",
    )
    assert first["run"] == "20260822T010000Z" and second["case"] == "(unknown case)"
    assert (first["estimated_cost_usd"], first["harness_reported_cost_usd"], first["turns"]) == (0.55, 0.66, 13)
    assert first["rates_applied"]["source"] == "/p/prices-20260820.toml"
    assert (first["accumulative_billed_tokens"], first["baseline_tokens"]) == (526_467, 22_956)
    # The billed sum and the peak prompt are different quantities; the row carries both so the
    # page never has to pair accumulative_billed_tokens with a context percentage.
    assert first["peak_context_tokens"] == 22_956 and "peak_context_tokens" in html
    assert "context_tokens" not in first and "billed_tokens" not in first
    assert first["has_ledger"] is True
    assert (second["session_id"], second["verdict"], second["log"], second["has_ledger"]) == (
        "01a022dc",
        None,
        None,
        False,
    )
    hint = page.serve_hint(CacheLayout(cache))
    assert "report/report.html" in hint and str(cache) in hint


def test_report_inline_embeds_data_and_user_design_tokens(tmp_path: Path) -> None:
    cache = tmp_path / ".xharness_eval_cache"
    session_dir = cache / "results" / "demo" / "claude" / "claude-opus-5" / "20260101T000000Z" / "sid1"
    session_dir.mkdir(parents=True)
    r = _result("claude-opus-5", Usage(1, 2, 3, 4))
    r.harness, r.session_id = "claude", "sid1"
    r.write(session_dir / "result.json")
    (session_dir / "log.jsonl").write_text('{"type":"user"}\n<script>alert(1)</script>\n', encoding="utf-8")
    brand = tmp_path / "brand.json"
    brand.write_text(
        json.dumps({"name": "acme", "themes": {"light": {"accent": "#ff0000"}, "dark": {"accent": "#00ff00"}}}),
        encoding="utf-8",
    )

    report_page = page.write(CacheLayout(cache), design_tokens=brand, inline=True)
    html = report_page.read_text(encoding="utf-8")
    assert "window.__XH_DATA__ = {" in html and page.INLINE_MARKER not in html
    assert '"name": "acme"' in json.dumps(
        json.loads((cache / "report" / "report.tokens.json").read_text(encoding="utf-8")), indent=1
    )
    # The payload carries the index, the result, the log and the tokens; a "</script>" in a log cannot end the tag.
    start = html.index("window.__XH_DATA__ = ") + len("window.__XH_DATA__ = ")
    payload = json.loads(html[start : html.index(";</script>", start)].replace("<\\/", "</"))
    assert payload["tokens"]["name"] == "acme"
    assert payload["index"]["inline"] is True and payload["index"]["cells"][0]["session_id"] == "sid1"
    assert payload["results"]["sid1"]["model"] == "claude-opus-5"
    assert "<script>alert(1)</script>" in payload["logs"]["sid1"]
    assert "<script>alert(1)</script>" not in html  # it is escaped as <\/script> inside the payload


def test_report_refuses_missing_or_malformed_design_tokens(tmp_path: Path) -> None:
    cache = tmp_path / ".xharness_eval_cache"
    cache.mkdir()
    with pytest.raises(FileNotFoundError, match="design tokens file not found"):
        page.write(CacheLayout(cache), design_tokens=tmp_path / "absent.json")
    bad = tmp_path / "bad.json"
    bad.write_text('{"colours": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="'themes' key"):
        page.write(CacheLayout(cache), design_tokens=bad)


def test_report_tolerates_an_empty_or_corrupt_results_tree(tmp_path: Path) -> None:
    cache = tmp_path / ".xharness_eval_cache"
    session_dir = cache / "results" / "s" / "h" / "m" / "20260101T000000Z" / "sid"
    session_dir.mkdir(parents=True)
    (session_dir / "result.json").write_text("not json", encoding="utf-8")
    (session_dir / "history.json").write_text("not json", encoding="utf-8")
    page.write(CacheLayout(cache))
    assert json.loads((cache / "report" / "index.json").read_text(encoding="utf-8"))["cells"] == []
    assert (cache / "report" / "history.jsonl").read_text(encoding="utf-8") == ""
    # A cache with no results/ at all still writes an empty report.
    empty = tmp_path / "empty-cache"
    page.write(CacheLayout(empty))
    assert json.loads((empty / "report" / "index.json").read_text(encoding="utf-8"))["cells"] == []

    # A stored record carrying a null where a string is declared: the combine step sorts
    # every record by ``at``, so a None there used to abort the whole report (ADR 0038).
    nulled = CacheLayout(tmp_path / "nulled-cache")
    session = nulled.session(skill="s", harness="h", model="m", run="20260101T000000Z", session="sid")
    session.mkdir()
    session.result.write_text('{"harness": "h", "session_id": "sid"}', encoding="utf-8")
    session.history.write_text('{"session_id": "sid", "at": null, "verdict": null}', encoding="utf-8")
    page.write(nulled)
    row = json.loads(nulled.index.read_text(encoding="utf-8"))["cells"][0]
    assert (row["session_id"], row["at"], row["verdict"]) == ("sid", "", "")
    assert json.loads(nulled.history.read_text(encoding="utf-8"))["at"] == ""
