"""Proof the content survived the edit: checks that compare the agent's file with its seed (ADR 0045).

A fixer's verdict is never "the tool is quiet" alone, because deleting the offending text
also quiets it. These checks are the other half of every such verdict, lifted from the
suites that each wrote their own:

* :func:`check_content_kept` -- the seed's content words survive, and no sentence went whole.
* :func:`check_length_kept` -- the prose was rewritten, not compressed.
* :func:`check_nothing_hidden` -- no prose was moved into code, which most gates skip.
* :func:`check_fences_kept` and :func:`check_ids_kept` -- no fence or named thing was removed.
* :func:`check_absent` and :func:`check_matches` -- a pattern is gone, or present.

Every comparison takes the seed as ``seed_text``, explicitly: the original is the
fixture's, and the grader names where it came from. For a generated scenario that is
``seed_text=output.seed("doc.md")``; for a committed fixture, the file's own text.

"Prose" here is the document with fenced code, inline code spans and HTML comments
removed, which is what a prose gate reads. Words are compared lowercased, stopwords
dropped, under a crude suffix stem, so a split that turns "has bumped" into "bumps"
keeps the word. Standard library only.
"""

from __future__ import annotations

# Standard Library
import re
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Callable, Iterable

    # Our Libraries
    from pytest_xharness_eval.model.output import CaseOutput

#: Words too common to carry a document's content. Splitting a sentence adds and drops
#: these freely, so they are left out of every recall figure.
_STOPWORD_TEXT = (
    "a an the and or but so yet nor of to in on at by for from with as into onto than then "
    "this that these those it its is are was were be been being has have had do does did "
    "which who whom whose when while if because although though unless where whereas "
    "not no every each both all any one also there their they them he she we you i"
)
STOPWORDS = frozenset(_STOPWORD_TEXT.split())

#: A whole fenced block, backticks or tildes, closed by the same fence.
_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,}).*?^[ \t]*\1[ \t]*$", re.MULTILINE | re.DOTALL)
#: One fence delimiter line, opening or closing.
_FENCE_LINE = re.compile(r"^[ \t]*(?:`{3,}|~{3,})", re.MULTILINE)
#: A fence's opening line; group 1 is its info string's first word.
_FENCE_OPEN = re.compile(r"^[ \t]*(`{3,}|~{3,})[ \t]*([^\s`]*)[^\n]*\n.*?^[ \t]*\1[ \t]*$", re.MULTILINE | re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`\n]+`")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_WORD = re.compile(r"[A-Za-z0-9_]+")
#: Where one sentence ends: terminal punctuation then space, or a line break.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
#: How many items a message quotes before eliding the rest.
_QUOTE = 20


def prose(doc: str) -> str:
    """The document with code fences, inline code and comments removed: what a prose gate reads."""
    return _INLINE_CODE.sub(" ", _COMMENT.sub(" ", _FENCE.sub(" ", doc)))


def words(text: str) -> list[str]:
    """Every word, lowercased."""
    return [w.lower() for w in _WORD.findall(text)]


def stem(word: str) -> str:
    """A crude suffix stem, never shorter than three letters."""
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def content_words(text: str) -> Counter[str]:
    """The words that carry content: every word but the stopwords, stemmed and counted."""
    return Counter(stem(w) for w in words(text) if w not in STOPWORDS)


def recall(seed: Counter[str], got: Counter[str]) -> float:
    """The share of the seed's words, counted with multiplicity, still present; 1.0 for none."""
    total = sum(seed.values())
    return 1.0 if total == 0 else sum(min(n, got[w]) for w, n in seed.items()) / total


def sentences(doc: str) -> list[str]:
    """The document's prose sentences, headings excluded."""
    lines = [line for line in prose(doc).splitlines() if not line.lstrip().startswith("#")]
    return [s.strip() for s in _SENTENCE_END.split("\n".join(lines)) if s.strip()]


def _compiled(pattern: str | re.Pattern[str]) -> re.Pattern[str]:
    """A plain string matches literally; a compiled pattern is used as it is."""
    return pattern if isinstance(pattern, re.Pattern) else re.compile(re.escape(pattern))


def _quoted(items: Iterable[object]) -> str:
    listed = list(items)
    more = f" ... and {len(listed) - _QUOTE} more" if len(listed) > _QUOTE else ""
    return f"{listed[:_QUOTE]}{more}"


def check_absent(output: CaseOutput, path: str, pattern: str | re.Pattern[str], *, why: str) -> None:
    """``pattern`` no longer occurs in ``path``. A string matches literally, a compiled regex as one.

    ``why`` is required: the reader of a red cell needs to know what the pattern stood for.
    """
    text = output.read(path)
    regex = _compiled(pattern)
    hits = [f"  {n}: {line.strip()}" for n, line in enumerate(text.splitlines(), 1) if regex.search(line)]
    if not hits and regex.search(text):
        hits = ["  (a match spans lines)"]
    assert not hits, f"{path} still contains {regex.pattern!r} ({why}):\n" + "\n".join(hits[:_QUOTE])


def check_matches(output: CaseOutput, path: str, pattern: str | re.Pattern[str], *, at_least: int = 1) -> None:
    """``pattern`` occurs in ``path`` at least ``at_least`` times. A string is a regex here."""
    regex = pattern if isinstance(pattern, re.Pattern) else re.compile(pattern, re.MULTILINE)
    found = len(regex.findall(output.read(path)))
    assert found >= at_least, f"{path} matches {regex.pattern!r} {found} time(s), fewer than the {at_least} required"


def check_content_kept(
    output: CaseOutput, path: str, seed_text: str, *, at_least: float = 0.9, per_sentence: float = 0.5
) -> None:
    """The seed's content words survive at ``at_least`` recall, and every seed sentence at ``per_sentence``.

    The whole-document figure catches a rewrite that drifted; the per-sentence floor
    catches the one that deleted a sentence outright, which a high overall recall hides.
    """
    got = content_words(prose(output.read(path)))
    seed = content_words(prose(seed_text))
    kept = recall(seed, got)
    missing = sorted((seed - got).elements())
    assert kept >= at_least, (
        f"{path} kept {kept:.0%} of the seed's content words, below {at_least:.0%}; gone: {_quoted(missing)}"
    )
    for sentence in sentences(seed_text):
        share = recall(content_words(sentence), got)
        assert share >= per_sentence, (
            f"{path} lost a seed sentence, keeping {share:.0%} of its content words "
            f"(floor {per_sentence:.0%}): {sentence!r}"
        )


def check_length_kept(output: CaseOutput, path: str, seed_text: str, *, ratio: tuple[float, float]) -> None:
    """The prose word count stays within ``ratio`` (lo, hi) of the seed's: rewritten, not compressed."""
    lo, hi = ratio
    got, want = len(words(prose(output.read(path)))), len(words(prose(seed_text)))
    assert lo * want <= got <= hi * want, (
        f"{path} has {got} prose words, the seed had {want}; the case allows {lo:.2f}x to {hi:.2f}x"
    )


def check_nothing_hidden(output: CaseOutput, path: str, seed_text: str) -> None:
    """No new code fence and no new inline code span: prose was not moved where a gate skips it.

    Wrapping an offending sentence in backticks zeroes most prose findings with no
    rewrite at all, so the counts may not grow past the seed's.
    """
    doc = output.read(path)
    fences, seed_fences = len(_FENCE_LINE.findall(doc)), len(_FENCE_LINE.findall(seed_text))
    spans, seed_spans = len(_INLINE_CODE.findall(doc)), len(_INLINE_CODE.findall(seed_text))
    assert fences <= seed_fences, f"{path} has {fences} fence line(s), the seed had {seed_fences}: prose hidden in code"
    assert spans <= seed_spans, (
        f"{path} has {spans} inline code span(s), the seed had {seed_spans}: prose hidden in code; "
        f"spans now: {_quoted(_INLINE_CODE.findall(doc))}"
    )


def _fence_langs(doc: str) -> list[str]:
    return [lang for _, lang in _FENCE_OPEN.findall(doc)]


def check_fences_kept(output: CaseOutput, path: str, seed_text: str, *, lang: str | None = None) -> None:
    """At least as many code fences (of ``lang``, when named) as the seed: none was removed to pass."""
    langs, seed_langs = _fence_langs(output.read(path)), _fence_langs(seed_text)
    got = len(langs) if lang is None else langs.count(lang)
    want = len(seed_langs) if lang is None else seed_langs.count(lang)
    kind = f"{lang} " if lang else ""
    assert got >= want, f"{path} has {got} {kind}fence(s), the seed had {want}: a block was removed"


def check_ids_kept(output: CaseOutput, path: str, seed_text: str, extractor: Callable[[str], Iterable[object]]) -> None:
    """Everything ``extractor`` finds in the seed is still found in ``path``.

    ``extractor`` is any ``str -> iterable``, typically a facet such as
    :func:`~pytest_xharness_eval.verify.facets.node_ids` or
    :func:`~pytest_xharness_eval.verify.facets.entities`.
    """
    missing = set(extractor(seed_text)) - set(extractor(output.read(path)))
    name = getattr(extractor, "__name__", "extractor")
    assert not missing, f"{len(missing)} {name} of the seed are gone from {path}: {_quoted(sorted(map(str, missing)))}"
