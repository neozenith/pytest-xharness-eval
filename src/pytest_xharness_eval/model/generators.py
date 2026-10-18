"""The fixture generators that ship: a table, a seeded draw, promoted failures, and an adversary (ADR 0074).

Each is a :class:`~pytest_xharness_eval.model.scenario.FixtureGenerator`, so a suite passes
one as ``@evalcase(fixture=...)`` and every scenario it yields becomes a cell:

* :class:`Table` -- one scenario per row of explicit parameters: the suite that was five
  near-identical files differing only in data becomes one case and five rows.
* :class:`Generated` -- ``count`` scenarios, each built from a seeded :class:`Draw`, for a
  parameter space too wide to enumerate.
* :class:`Promoted` -- every failure a sweep found and ``python -m
  pytest_xharness_eval.promote`` froze into ``evals/fixtures/``: the regression suite.
* :class:`Adversarial` -- mutants of a seed generator's scenarios, spent where the subject
  already breaks, screened by a free oracle before any of them costs a run.

The search an adversary runs is deliberately small. A cell costs cents to dollars, so the
budget is tens of runs, not the millions a fuzzer spends; what makes that enough is the
free oracle (a linter's rule ids, a parser's verdict) deciding which mutants are worth a
paid run at all, and history deciding which seeds to mutate.
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Final

# Our Libraries
from pytest_xharness_eval.model.scenario import MUTATION_KEY, Draw, Files, Scenario, ScenarioStore, read_tree

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.model.scenario import FixtureGenerator, GenerationContext

    #: Builds one scenario's files from its parameters.
    Build = Callable[[Mapping[str, Any]], Files]
    #: Draws one scenario's parameters and files.
    DrawBuild = Callable[[Draw], tuple[Mapping[str, Any], Files]]
    #: A free, deterministic check of a file tree: the set of signals it raises (rule ids, say).
    Oracle = Callable[[Files], frozenset[str]]


@dataclass(frozen=True, slots=True, kw_only=True)
class Table:
    """One scenario per row: ``build(row)`` is the row's files, ``row`` its parameters.

    ``label`` names the row key whose value labels the scenario id; ``task`` is a format
    string over the row (``"Fix {target}"``), for a case whose instruction names its file.
    ``expect`` names the row keys that are grader knobs rather than what the scenario is:
    they reach the grader but not the id, so tuning one keeps the scenario's history.
    """

    name: str
    rows: Sequence[Mapping[str, Any]]
    build: Build
    version: int = 1
    label: str | None = None
    task: str | None = None
    expect: Sequence[str] = ()
    #: A table with no rows is a broken suite, not an answer.
    may_be_empty: ClassVar[bool] = False

    def scenarios(self, context: GenerationContext) -> Iterator[Scenario]:
        knobs = set(self.expect)
        for row in self.rows:
            missing = sorted(knobs - set(row))
            if missing:
                raise KeyError(f"{self.name}: row {dict(row)} lacks the expectation keys {missing}")
            yield Scenario(
                generator=self.name,
                version=self.version,
                params={k: v for k, v in row.items() if k not in knobs},
                expect={k: v for k, v in row.items() if k in knobs},
                files=self.build(row),
                label=str(row[self.label]) if self.label else None,
                task=self.task.format(**row) if self.task else None,
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class Generated:
    """``count`` scenarios, the ``i``-th drawn from ``Draw(name, version, seed, i)``.

    The same ``(name, version, seed)`` draws the same scenarios on every machine and Python
    version, so a cell id from last week's sweep still names the same input.
    """

    name: str
    build: DrawBuild
    count: int
    seed: int = 0
    version: int = 1
    task: str | None = None
    #: A draw of nothing is a broken suite, not an answer.
    may_be_empty: ClassVar[bool] = False

    def scenarios(self, context: GenerationContext) -> Iterator[Scenario]:
        for i in range(self.count):
            params, files = self.build(Draw(self.name, self.version, self.seed, i))
            row = dict(params)
            yield Scenario(
                generator=self.name,
                version=self.version,
                params=row,
                files=files,
                label=str(row.get("label") or f"{self.name}-{i}"),
                task=self.task.format(**row) if self.task else None,
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class Promoted:
    """Every fixture under ``evals/fixtures/`` that was promoted from a generator named ``source``.

    A promoted fixture is a directory of frozen bytes with a ``<dir>.provenance.json`` beside
    it naming the generator, the parameters and the fingerprint. ``source=None`` takes every
    promoted fixture. A regression case is declared before its first failure is promoted, so
    finding none is allowed: collection names the empty case in a warning rather than
    reporting a green sweep that guarded nothing in silence (:attr:`may_be_empty`).
    """

    name: str
    source: str | None = None
    may_be_empty: ClassVar[bool] = True

    def scenarios(self, context: GenerationContext) -> list[Scenario]:
        # A suite's committed fixtures are a scenario store once a failure is promoted into it.
        found = [Scenario.promoted(tree) for tree in ScenarioStore(context.evals_dir / "fixtures").stored().values()]
        return [s for s in found if self.source is None or s.generator == self.source]


def _name(fn: Callable[..., Any]) -> str:
    return str(getattr(fn, "__name__", type(fn).__name__))


@dataclass(frozen=True, slots=True, kw_only=True)
class Adversarial:
    """Mutants of ``seeds``' scenarios, aimed where the subject already fails (ADR 0074).

    Each sweep yields at most ``budget`` scenarios:

    1. **Confirm.** Past mutants that failed and are still stored are re-run from their bytes,
       worst first, up to half the budget, so one unlucky sample is never promoted as a
       regression.
    2. **Explore.** The rest are mutants this case has never sampled. A parent is drawn with
       weight ``(f + 1) / (n + 2)`` -- the posterior mean failure rate under a uniform prior,
       counting the samples of every stored mutant bred from it -- so a seed whose offspring
       broke the subject is mutated more, and an untried seed still gets a fair share. Each
       mutant applies one to ``depth`` distinct mutators. The draws are salted with the
       number of mutants already sampled, so each sweep explores somewhere new.
    3. **Screen.** With an ``oracle``, a mutant is kept only if its signal set is non-empty
       and new to this sweep, so the paid budget goes to inputs that differ in kind.

    A mutant's ``params`` are its parent's, plus a ``mutation`` record of where it came from,
    so a grader reads ``output.params`` the same way for a seed and for its mutants. Its
    ``expect`` is its parent's.

    Deterministic for a given history, seed and generator code. When the search finds nothing
    new and nothing failed, it yields nothing; collection reports that by name rather than
    aborting the sweep (:attr:`may_be_empty`).
    """

    name: str
    seeds: FixtureGenerator
    mutators: Sequence[Callable[[Files, Draw], Files]]
    budget: int
    seed: int = 0
    depth: int = 2
    oracle: Oracle | None = None
    version: int = 1
    #: Mutants drawn per kept scenario before the search gives up.
    attempts: int = 20
    #: An exhausted search is an answer, not a broken suite.
    may_be_empty: ClassVar[bool] = True

    def scenarios(self, context: GenerationContext) -> list[Scenario]:
        if not self.mutators:
            raise ValueError(f"{self.name}: an adversarial generator needs at least one mutator")
        parents = list(self.seeds.scenarios(context))
        if not parents:
            raise ValueError(f"{self.name}: its seed generator {self.seeds.name} yielded no scenarios")
        confirm = self._confirm(context)
        sampled = {sid for sid in context.outcomes if sid in context.stored}
        taken = {s.id for s in confirm} | sampled
        return confirm + self._explore(parents, context, self.budget - len(confirm), taken, generation=len(sampled))

    def _confirm(self, context: GenerationContext) -> list[Scenario]:
        """Stored past mutants of this generator that failed, worst first, up to half the budget."""
        stored = context.stored
        failed = [
            (fails / runs, sid)
            for sid, (fails, runs) in context.outcomes.items()
            if fails
            and sid in stored
            and context.store is not None
            and context.store.provenance(sid).generator == self.name
        ]
        chosen = [sid for _, sid in sorted(failed, key=lambda x: (-x[0], x[1]))][: self.budget // 2]
        return [Scenario.promoted(stored[sid]) for sid in chosen]

    def _explore(
        self, parents: list[Scenario], context: GenerationContext, room: int, taken: set[str], *, generation: int
    ) -> list[Scenario]:
        lineage = _lineage(context)
        weights = [(lineage.get(p.id, (0, 0))[0] + 1) / (lineage.get(p.id, (0, 0))[1] + 2) for p in parents]
        seen: set[frozenset[str]] = set()
        kept: list[Scenario] = []
        for attempt in range(max(room, 0) * self.attempts):
            if len(kept) >= room:
                break
            draw = Draw(self.name, self.version, self.seed, generation, attempt)
            parent = _weighted(parents, weights, draw)
            picks = [self.mutators[draw.integer(0, len(self.mutators) - 1)] for _ in range(draw.integer(1, self.depth))]
            # The same mutator twice is usually idempotent: a wasted draw, not a deeper mutant.
            chain = list({_name(m): m for m in picks}.values())
            files: Files = dict(parent.files)
            for mutate in chain:
                files = mutate(files, draw)
            child = self._child(parent, chain, files, generation, attempt)
            if (
                child.id in taken
                or child.fingerprint == parent.fingerprint
                or any(k.fingerprint == child.fingerprint for k in kept)
            ):
                continue
            if self.oracle is not None:
                signals = self.oracle(files)
                if not signals or signals in seen:
                    continue
                seen.add(signals)
            kept.append(child)
        return kept

    def _child(
        self, parent: Scenario, chain: list[Callable[[Files, Draw], Files]], files: Files, generation: int, attempt: int
    ) -> Scenario:
        names = [_name(m) for m in chain]
        mutation = {"parent": parent.id, "mutators": names, "generation": generation, "attempt": attempt}
        return Scenario(
            generator=self.name,
            version=self.version,
            params={**parent.params, MUTATION_KEY: mutation},
            expect=dict(parent.expect),
            files=files,
            label=f"{parent.label or parent.generator}-{'-'.join(names)}",
            task=parent.task,
        )


def _lineage(context: GenerationContext) -> dict[str, tuple[int, int]]:
    """``(failed, sampled)`` per scenario id, each stored mutant's samples also credited to its parent."""
    out = dict(context.outcomes)
    parents = context.store.lineage() if context.store is not None else {}
    for sid, (failed, sampled) in context.outcomes.items():
        parent = parents.get(sid)
        if parent is not None:
            f, n = out.get(parent, (0, 0))
            out[parent] = (f + failed, n + sampled)
    return out


def _weighted(items: Sequence[Scenario], weights: Sequence[float], draw: Draw) -> Scenario:
    """One of ``items``, drawn with probability proportional to its weight."""
    point = draw.random() * sum(weights)
    for item, weight in zip(items, weights, strict=True):
        point -= weight
        if point < 0:
            return item
    return items[-1]


# -- mutators: generic text perturbations an adversary composes ------------------------

#: The files a text mutator touches by default: prose and diagram sources.
TEXT_SUFFIXES: Final = (".md", ".mmd", ".markdown", ".txt")


def _text(content: str | bytes) -> str | None:
    """``content`` as text: a string as it is, bytes when they decode as UTF-8, else None."""
    if isinstance(content, str):
        return content
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _texts(files: Files, suffixes: Iterable[str]) -> list[str]:
    """The text files a mutator may touch: matching suffix, and readable as UTF-8 (a seed from
    :func:`read_tree` is bytes, and skipping it would leave an adversary mutating nothing)."""
    ends = tuple(suffixes)
    return sorted(p for p, c in files.items() if p.endswith(ends) and _text(c) is not None)


@dataclass(frozen=True, slots=True)
class TextMutator:
    """A named text-to-text perturbation applied to one drawn text file of the tree."""

    name: str
    apply: Callable[[str, Draw], str]
    suffixes: tuple[str, ...] = field(default=TEXT_SUFFIXES)

    @property
    def __name__(self) -> str:  # noqa: PLW3201 - the name an adversary records, as for a function
        return self.name

    def __call__(self, files: Files, draw: Draw) -> Files:
        targets = _texts(files, self.suffixes)
        if not targets:
            return files
        path = draw.choice(targets)
        out = dict(files)
        out[path] = self.apply(_text(files[path]) or "", draw)
        return out


def _crlf(text: str, _: Draw) -> str:
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def _trailing_whitespace(text: str, draw: Draw) -> str:
    return "\n".join(
        line + (" " * draw.integer(1, 3) if line and draw.chance(0.4) else "") for line in text.split("\n")
    )


def _zero_width(text: str, draw: Draw) -> str:
    words = text.split(" ")
    for _ in range(max(1, len(words) // 20)):
        i = draw.integer(0, len(words) - 1)
        words[i] = words[i] + "​"
    return " ".join(words)


def _duplicate_paragraph(text: str, draw: Draw) -> str:
    paragraphs = text.split("\n\n")
    i = draw.integer(0, len(paragraphs) - 1)
    return "\n\n".join([*paragraphs[: i + 1], paragraphs[i], *paragraphs[i + 1 :]])


def _shuffle_paragraphs(text: str, draw: Draw) -> str:
    head, *rest = text.split("\n\n")
    return "\n\n".join([head, *draw.shuffled(rest)])


def _no_final_newline(text: str, _: Draw) -> str:
    return text.rstrip("\n")


def _nbsp(text: str, draw: Draw) -> str:
    return "".join(" " if ch == " " and draw.chance(0.05) else ch for ch in text)


#: The text mutators that ship, each a structural or encoding perturbation a linter-fixing
#: agent should survive without changing what the document says.
CRLF: Final = TextMutator("crlf", _crlf)
TRAILING_WHITESPACE: Final = TextMutator("trailing_whitespace", _trailing_whitespace)
ZERO_WIDTH: Final = TextMutator("zero_width", _zero_width)
DUPLICATE_PARAGRAPH: Final = TextMutator("duplicate_paragraph", _duplicate_paragraph)
SHUFFLE_PARAGRAPHS: Final = TextMutator("shuffle_paragraphs", _shuffle_paragraphs)
NO_FINAL_NEWLINE: Final = TextMutator("no_final_newline", _no_final_newline)
NBSP: Final = TextMutator("nbsp", _nbsp)

TEXT_MUTATORS: Final = (
    CRLF,
    TRAILING_WHITESPACE,
    ZERO_WIDTH,
    DUPLICATE_PARAGRAPH,
    SHUFFLE_PARAGRAPHS,
    NO_FINAL_NEWLINE,
    NBSP,
)


def from_dir(name: str, root: Path, *, transform: Callable[[str, str], str] | None = None) -> Table:
    """One scenario per subdirectory of ``root``, its files read as text and optionally transformed.

    ``transform(path, text)`` rewrites each text file -- stripping an ``<!-- expect: -->``
    marker from a linter's own rule fixture, say -- so a suite reuses material the subject's
    own tests already keep instead of committing a hand-edited copy of it.
    """
    dirs = sorted(p for p in root.iterdir() if p.is_dir())
    if not dirs:
        raise FileNotFoundError(f"{root} has no subdirectories to generate scenarios from")

    def build(row: Mapping[str, Any]) -> Files:
        files: Files = {}
        for rel, raw in read_tree(root / str(row["dir"])).items():
            text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            files[rel] = transform(rel, text) if transform else text
        return files

    return Table(name=name, rows=[{"dir": d.name} for d in dirs], build=build, label="dir")
