"""Every path under a project's eval cache, named in one place (ADR 0032, ADR 0037).

The cache tree is a published contract, not an implementation detail: the report page
fetches ``../results/{skill}/{harness}/{model}/{run}/{session}/log.jsonl`` by that exact
shape, and a replay finds a capture by walking it. It used to be spelled out in five
modules at once -- ``HISTORY_NAME`` meant ``history.json`` in ``pipeline`` and
``history.jsonl`` in ``report``, the five-level glob was written three times, both harness
adapters hardcoded ``log.jsonl``, and ``Settings.results_root`` was a third spelling of
``<cache>/results`` -- so no rename could be made in one edit.

Every type here is a value object over a path: frozen, holding no state, and touching the
filesystem only to list a tree or create a directory. Nothing here reads or writes a
document; the documents own their own formats (``metrics.CellMetrics``,
``runresult.RunResult``, ``report.IndexRow``).
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterator
    from pathlib import Path

# Directories directly under the cache root.
BUILD_DIR = "build"
RESULTS_DIR = "results"
REPORT_DIR = "report"

# One session's evidence (ADR 0032). ``HISTORY_NAME`` is *one* session's metrics record;
# the aggregate of all of them is ``AGGREGATED_HISTORY_NAME`` below, and the two names are
# deliberately not interchangeable.
LOG_NAME = "log.jsonl"
RESULT_NAME = "result.json"
HISTORY_NAME = "history.json"
SUBAGENTS_DIR = "subagents"

# The microsite the combine step writes, and the bundled assets it ships (ADR 0020).
INDEX_NAME = "index.json"
AGGREGATED_HISTORY_NAME = "history.jsonl"
SUMMARY_NAME = "report.json"
PAGE_NAME = "report.html"
TOKENS_NAME = "report.tokens.json"
GLOSSARY_NAME = "XHARNESS-REPORT-GLOSSARY.md"


@dataclass(frozen=True, slots=True)
class SessionDir:
    """One cell's evidence directory, addressed by path alone.

    A cell writes only inside its own directory, which is what makes parallel workers
    conflict-free (ADR 0032). The four names it may hold are addressed through the
    properties below, so a harness re-reading its own captured log, the combine step
    indexing it and a replay rebuilding it all spell them the same way.

    This is the type for a caller *handed* a directory -- a replay rebuilding one session,
    an adapter folding its own captured log -- and it deliberately cannot produce a report
    link, because a bare path does not know where it sits in a cache. The type that can is
    :class:`LocatedSession`, and only :class:`CacheLayout` builds one (ADR 0038).
    """

    path: Path

    @property
    def session(self) -> str:
        """The session id: the directory is named for it."""
        return self.path.name

    @property
    def log(self) -> Path:
        """The session log, verbatim as the harness wrote it."""
        return self.path / LOG_NAME

    @property
    def result(self) -> Path:
        """The normalised :class:`~pytest_xharness_eval.runresult.RunResult`."""
        return self.path / RESULT_NAME

    @property
    def history(self) -> Path:
        """This session's one :class:`~pytest_xharness_eval.metrics.CellMetrics` record."""
        return self.path / HISTORY_NAME

    @property
    def subagents(self) -> Path:
        """Where the transcripts of the threads this session spawned are captured (ADR 0033)."""
        return self.path / SUBAGENTS_DIR

    def mkdir(self) -> Path:
        """Create the directory and its parents, and return it."""
        self.path.mkdir(parents=True, exist_ok=True)
        return self.path


@dataclass(frozen=True, slots=True, kw_only=True)
class LocatedSession(SessionDir):
    """A :class:`SessionDir` that knows its five coordinates under ``results/``.

    The tree's five levels *are* a session's identity, so a located directory -- and only a
    located one -- can be named by :attr:`rel` and linked to from the report page. The
    coordinates are always all known: :meth:`CacheLayout.session` is handed them and
    :meth:`CacheLayout.sessions` reads them off the walk, and there is no third
    constructor. One type served both jobs until ADR 0038, with the coordinates defaulting
    to empty strings, which made ``"////sid"`` a representable key and
    ``"../results/////sid/log.jsonl"`` a publishable link.
    """

    skill: str
    harness: str
    model: str
    run: str

    @property
    def rel(self) -> str:
        """``{skill}/{harness}/{model}/{run}/{session}``: the coordinates as one posix key."""
        return "/".join((self.skill, self.harness, self.model, self.run, self.session))

    @property
    def report_link_prefix(self) -> str:
        """The path from ``report/`` to this directory: the page fetches relative (ADR 0032)."""
        return f"../{RESULTS_DIR}/{self.rel}"

    def report_link(self, name: str) -> str:
        """The path from ``report/`` to one of this session's files."""
        return f"{self.report_link_prefix}/{name}"


@dataclass(frozen=True, slots=True)
class CacheLayout:
    """``<cache>/``: the git-ignored root every run output lives under (ADR 0032).

    Three subtrees, and one owner for all of them: ``build/`` holds the per-cell
    workspaces, ``results/`` the per-session evidence, and ``report/`` the aggregated
    microsite the combine step writes.
    """

    root: Path

    # -- the three subtrees ------------------------------------------------------------

    @property
    def build(self) -> Path:
        """``<cache>/build/``: one materialised workspace per cell."""
        return self.root / BUILD_DIR

    @property
    def results(self) -> Path:
        """``<cache>/results/``: one :class:`LocatedSession` five levels beneath it."""
        return self.root / RESULTS_DIR

    @property
    def report(self) -> Path:
        """``<cache>/report/``: the aggregated microsite."""
        return self.root / REPORT_DIR

    # -- the evidence tree -------------------------------------------------------------

    def session(self, *, skill: str, harness: str, model: str, run: str, session: str) -> LocatedSession:
        """The evidence directory for one cell of one run, named by its five coordinates."""
        return LocatedSession(
            self.results / skill / harness / model / run / session,
            skill=skill,
            harness=harness,
            model=model,
            run=run,
        )

    def sessions(self) -> Iterator[LocatedSession]:
        """Every captured session directory under ``results/``, in path order.

        The five-level walk lives here and nowhere else. The index, the aggregated history
        and the replay each carried their own copy of the glob and each re-derived the
        coordinates from the relative path (ADR 0037). A caller checks for the document it
        needs: a directory holding no ``result.json`` is a partial capture, not an error.
        """
        results = self.results
        for path in sorted(results.glob("*/*/*/*/*")):
            if not path.is_dir():
                continue
            skill, harness, model, run, _session = path.relative_to(results).parts
            yield LocatedSession(path, skill=skill, harness=harness, model=model, run=run)

    # -- the microsite -----------------------------------------------------------------

    @property
    def index(self) -> Path:
        """``report/index.json``: one :class:`~pytest_xharness_eval.report.IndexRow` per session."""
        return self.report / INDEX_NAME

    @property
    def history(self) -> Path:
        """``report/history.jsonl``: every session's metrics record, combined."""
        return self.report / AGGREGATED_HISTORY_NAME

    @property
    def summary(self) -> Path:
        """``report/report.json``: this pytest session's own cells and total spend."""
        return self.report / SUMMARY_NAME

    @property
    def page(self) -> Path:
        """``report/report.html``: the browsable page."""
        return self.report / PAGE_NAME

    @property
    def tokens(self) -> Path:
        """``report/report.tokens.json``: the design tokens the page is themed with."""
        return self.report / TOKENS_NAME

    @property
    def glossary(self) -> Path:
        """``report/XHARNESS-REPORT-GLOSSARY.md``: the names of everything on the page."""
        return self.report / GLOSSARY_NAME
