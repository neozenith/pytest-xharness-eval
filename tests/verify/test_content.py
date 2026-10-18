"""``verify.content``: proof the agent's file kept its seed's content, and hid nothing (ADR 0045)."""

from __future__ import annotations

# Standard Library
import re
import textwrap
from typing import TYPE_CHECKING

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import CaseOutput, Usage, verify
from pytest_xharness_eval.verify import content, facets
from tests.support import _result

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path

SEED = textwrap.dedent(
    """\
    # Release notes

    The deployment pipeline has bumped every service version, which broke the staging cluster for an afternoon.
    Operators restarted the queue workers manually.

    ```mermaid
    flowchart TD
        Build --> Deploy
    ```
    """
)

#: A faithful rewrite: the long sentence split in two, nothing lost, nothing hidden.
SPLIT = SEED.replace(
    "The deployment pipeline has bumped every service version, which broke the staging cluster for an afternoon.",
    "The deployment pipeline bumps every service version. That broke the staging cluster for an afternoon.",
)


def _output(tmp_path: Path, doc: str) -> CaseOutput:
    workspace = tmp_path / "ws"
    workspace.mkdir(exist_ok=True)
    (workspace / "NOTES.md").write_text(doc, encoding="utf-8")
    return CaseOutput(run=_result("m", Usage()), workspace=workspace)


def test_the_prose_reading_drops_code_and_comments() -> None:
    doc = "Keep this `drop` <!-- gone --> word.\n```\ncode line\n```\n"
    assert content.words(content.prose(doc)) == ["keep", "this", "word"]
    assert content.stem("bumped") == content.stem("bumps") == "bump"
    assert content.stem("is") == "is"
    assert content.recall(content.content_words(""), content.content_words("x")) == 1.0


def test_a_faithful_split_keeps_content_and_length(tmp_path: Path) -> None:
    out = _output(tmp_path, SPLIT)
    verify.check_content_kept(out, "NOTES.md", SEED, at_least=0.9)
    verify.check_length_kept(out, "NOTES.md", SEED, ratio=(0.8, 1.3))
    verify.check_nothing_hidden(out, "NOTES.md", SEED)
    verify.check_fences_kept(out, "NOTES.md", SEED, lang="mermaid")
    verify.check_ids_kept(out, "NOTES.md", SEED, facets.node_ids)


def test_a_deleted_sentence_fails_even_when_overall_recall_is_high(tmp_path: Path) -> None:
    """A high whole-document recall hides one sentence removed outright."""
    out = _output(tmp_path, SEED.replace("Operators restarted the queue workers manually.\n", ""))
    with pytest.raises(AssertionError, match="lost a seed sentence.*Operators restarted"):
        verify.check_content_kept(out, "NOTES.md", SEED, at_least=0.5)
    with pytest.raises(AssertionError, match=r"kept \d+% of the seed's content words, below 95%; gone: .*operator"):
        verify.check_content_kept(out, "NOTES.md", SEED, at_least=0.95)


def test_compression_fails_the_length_ratio(tmp_path: Path) -> None:
    out = _output(tmp_path, "# Release notes\n\nPipeline broke staging.\n")
    with pytest.raises(AssertionError, match=r"has 5 prose words, the seed had \d+"):
        verify.check_length_kept(out, "NOTES.md", SEED, ratio=(0.8, 1.2))


def test_prose_moved_into_code_is_caught(tmp_path: Path) -> None:
    """Wrapping a sentence in backticks zeroes a prose gate with no rewrite at all."""
    spans = SEED.replace("Operators restarted the queue workers manually.", "`Operators restarted the queue workers.`")
    with pytest.raises(AssertionError, match=r"1 inline code span\(s\), the seed had 0"):
        verify.check_nothing_hidden(_output(tmp_path, spans), "NOTES.md", SEED)
    fenced = SEED + "\n```\nOperators restarted the queue workers manually.\n```\n"
    with pytest.raises(AssertionError, match=r"4 fence line\(s\), the seed had 2"):
        verify.check_nothing_hidden(_output(tmp_path, fenced), "NOTES.md", SEED)


def test_a_removed_fence_or_node_is_caught(tmp_path: Path) -> None:
    no_fence = SEED.split("```mermaid")[0]
    out = _output(tmp_path, no_fence)
    with pytest.raises(AssertionError, match=r"0 mermaid fence\(s\), the seed had 1"):
        verify.check_fences_kept(out, "NOTES.md", SEED, lang="mermaid")
    with pytest.raises(AssertionError, match=r"0 fence\(s\), the seed had 1"):
        verify.check_fences_kept(out, "NOTES.md", SEED)
    renamed = _output(tmp_path, SEED.replace("Deploy", "Ship"))
    with pytest.raises(AssertionError, match=r"1 node_ids of the seed are gone.*Deploy"):
        verify.check_ids_kept(renamed, "NOTES.md", SEED, facets.node_ids)


def test_absent_matches_literally_unless_compiled(tmp_path: Path) -> None:
    out = _output(tmp_path, SEED)
    verify.check_absent(out, "NOTES.md", "bumped.", why="never matches as a regex here")
    with pytest.raises(AssertionError, match=r"still contains 'Operators' \(the old name\):\n  4: Operators"):
        verify.check_absent(out, "NOTES.md", "Operators", why="the old name")
    with pytest.raises(AssertionError, match="a match spans lines"):
        verify.check_absent(out, "NOTES.md", re.compile(r"afternoon\.\nOperators"), why="a run-on")


def test_matches_counts_regex_hits(tmp_path: Path) -> None:
    out = _output(tmp_path, SEED)
    verify.check_matches(out, "NOTES.md", r"^# ", at_least=1)
    verify.check_matches(out, "NOTES.md", re.compile(r"service"), at_least=1)
    with pytest.raises(AssertionError, match=r"cluster.* 1 time\(s\), fewer than the 2"):
        verify.check_matches(out, "NOTES.md", r"\bcluster\b", at_least=2)


def test_sentences_split_on_punctuation_and_skip_headings() -> None:
    assert content.sentences("# Title\n\nOne here. Two there!\nThree\n") == ["One here.", "Two there!", "Three"]
