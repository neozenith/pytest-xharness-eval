"""A generated fixture: one scenario a case runs on, and the protocol that produces them (ADR 0074).

A committed fixture is a directory someone wrote by hand. A suite that wants twenty of them
that differ only in data used to commit twenty directories and twenty near-identical case
functions. A :class:`FixtureGenerator` is the alternative: Python that yields
:class:`Scenario` values, each a file tree plus the parameters that produced it, which the
grader reads back as ``output.scenario``.

Three properties make a generated scenario as trustworthy as a committed one:

* **A stable id.** The id is a readable slug and a digest of the generator's name, version
  and canonical parameters -- never a list position or a counter, which renumber when a row
  is inserted. The id joins the cell's node id, so ``-k`` and a replay address it directly.
* **A recorded fingerprint.** The digest of the bytes the scenario wrote. Two records of
  one id with different fingerprints measured different inputs, and the Analyzer never
  pools them; a generator whose output changes for the same parameters bumps ``version``.
* **Reproducible randomness.** :class:`Draw` derives its seed from a digest (never
  ``hash()``, which ``PYTHONHASHSEED`` salts per process) and draws only through
  :meth:`random.Random.random`, the one method whose sequence Python promises to keep.
"""

from __future__ import annotations

# Standard Library
import hashlib
import json
import os
import random
import re
import shutil
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Final, Protocol, Self, runtime_checkable

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterable, Mapping, Sequence
    from pathlib import Path

#: A scenario's files: workspace-relative POSIX path to its text or bytes.
Files = dict[str, str | bytes]

#: The provenance file a promoted scenario keeps *beside* its fixture directory, never inside
#: it: anything inside a fixture is copied into every workspace (ADR 0018).
PROVENANCE_SUFFIX: Final = ".provenance.json"

_SLUG: Final = re.compile(r"[^a-z0-9]+")
_SKIPPED: Final = frozenset({"__pycache__", "node_modules", ".git"})


def canonical(value: Any) -> str:
    """``value`` as canonical JSON: sorted keys, no whitespace, so equal params digest equally."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def digest(*parts: Any) -> str:
    """The sha256 hex digest of ``parts`` in canonical JSON."""
    return hashlib.sha256(canonical(list(parts)).encode("utf-8")).hexdigest()


def slug(text: str, limit: int = 40) -> str:
    """``text`` lowercased to ``[a-z0-9-]``, at most ``limit`` characters."""
    return _SLUG.sub("-", text.lower()).strip("-")[:limit].strip("-") or "scenario"


def _bytes(content: str | bytes) -> bytes:
    return content.encode("utf-8") if isinstance(content, str) else content


def fingerprint(files: Mapping[str, str | bytes]) -> str:
    """The digest of a file tree: every path and its bytes, in path order."""
    h = hashlib.sha256()
    for path in sorted(files):
        h.update(path.encode("utf-8") + b"\0" + _bytes(files[path]) + b"\0")
    return h.hexdigest()


def read_tree(root: Path) -> Files:
    """Every file under ``root`` as a :data:`Files` map, skipping caches and vendored trees.

    The way a generator starts from material already on disk -- a linter's own rule fixtures,
    say -- and transforms it, rather than committing a second hand-edited copy.
    """
    if not root.is_dir():
        raise FileNotFoundError(f"not a directory: {root}")
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not _SKIPPED.intersection(p.relative_to(root).parts)
    }


def write_tree(files: Mapping[str, str | bytes], dest: Path) -> Path:
    """Write ``files`` under ``dest``, which is emptied first so no stale file survives."""
    if dest.exists():
        for p in sorted(dest.rglob("*"), reverse=True):
            p.unlink() if p.is_file() or p.is_symlink() else p.rmdir()
    dest.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        target = dest / rel
        if target.resolve().parent != dest.resolve() and dest.resolve() not in target.resolve().parents:
            raise ValueError(f"scenario path escapes its fixture: {rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_bytes(content))
    return dest


class Draw:
    """A seeded source of choices that stays reproducible across Python versions.

    Every method is built on :meth:`random.Random.random` alone: ``choice``, ``shuffle`` and
    ``randrange`` may change their sequences between Python releases, ``random()`` may not.
    """

    def __init__(self, *seed: Any) -> None:
        self._rng = random.Random(int(digest(*seed)[:16], 16))

    def random(self) -> float:
        """A float in ``[0, 1)``."""
        return self._rng.random()

    def integer(self, low: int, high: int) -> int:
        """An integer in ``[low, high]``, both ends included."""
        return low + min(int(self._rng.random() * (high - low + 1)), high - low)

    def choice[T](self, options: Sequence[T]) -> T:
        """One of ``options``."""
        if not options:
            raise ValueError("cannot choose from no options")
        return options[self.integer(0, len(options) - 1)]

    def chance(self, p: float) -> bool:
        """True with probability ``p``."""
        return self._rng.random() < p

    def shuffled[T](self, items: Sequence[T]) -> list[T]:
        """A new list of ``items`` in a drawn order (Fisher-Yates over :meth:`random`)."""
        out = list(items)
        for i in range(len(out) - 1, 0, -1):
            j = self.integer(0, i)
            out[i], out[j] = out[j], out[i]
        return out

    def sample[T](self, items: Sequence[T], k: int) -> list[T]:
        """``k`` distinct items, in drawn order."""
        return self.shuffled(items)[:k]


@dataclass(frozen=True, slots=True, kw_only=True)
class Scenario:
    """One generated fixture: a file tree, the parameters that made it, and its identity.

    ``params`` are what the scenario *is*: they are digested into the id. ``expect`` are what
    the grader holds it to -- a recall threshold, a length ratio -- and are deliberately not
    in the id, so tuning a tolerance keeps the scenario's history in one piece. Both must be
    JSON-able; the grader reads them merged, as ``output.params``. ``task`` overrides the
    case's own task for this scenario only, for a scenario whose instruction names its file.
    """

    generator: str
    params: Mapping[str, Any]
    files: Mapping[str, str | bytes]
    version: int = 1
    label: str | None = None
    task: str | None = None
    expect: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # A non-JSON param fails at construction, not at the record. Strictly: ``canonical``'s
        # ``default=str`` would let a set or an object through as a string whose order or
        # address changes per process, and the id with it.
        try:
            json.dumps([self.params, self.expect], sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"scenario {self.generator}: params must be JSON-able: {exc}") from exc
        if not self.files:
            raise ValueError(f"scenario {self.generator}:{self.label or self.params} has no files")
        clash = sorted(set(self.params) & set(self.expect))
        if clash:
            raise ValueError(f"scenario {self.generator}: {clash} is both a param and an expectation")

    @property
    def merged(self) -> dict[str, Any]:
        """Params and expectations in one mapping: what the grader reads as ``output.params``."""
        return {**self.params, **self.expect}

    @property
    def key(self) -> str:
        """The digest of generator, version and canonical params: what the id is pinned to."""
        return digest(self.generator, self.version, self.params)

    @property
    def id(self) -> str:
        """``<slug>--<8 hex>``: readable, and stable while generator, version and params are."""
        return f"{slug(self.label or canonical(self.params))}--{self.key[:8]}"

    @property
    def fingerprint(self) -> str:
        """The digest of the bytes this scenario writes."""
        return fingerprint(self.files)

    def write(self, dest: Path) -> Path:
        """Write the file tree under ``dest``."""
        return write_tree(self.files, dest)

    def provenance(self) -> dict[str, Any]:
        """What a promoted copy of this scenario keeps beside its committed bytes."""
        return {
            "generator": self.generator,
            "version": self.version,
            "id": self.id,
            "label": self.label,
            "params": dict(self.params),
            "expect": dict(self.expect),
            "task": self.task,
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def promoted(cls, fixture: Path) -> Self:
        """The scenario a promoted fixture directory holds, read with its provenance file."""
        meta = json.loads(fixture.with_name(fixture.name + PROVENANCE_SUFFIX).read_text(encoding="utf-8"))
        scenario = cls(
            generator=str(meta["generator"]),
            version=int(meta["version"]),
            params=dict(meta["params"]),
            files=read_tree(fixture),
            label=meta.get("label"),
            task=meta.get("task"),
            expect=dict(meta.get("expect") or {}),
        )
        if scenario.fingerprint != meta["fingerprint"]:
            raise ValueError(
                f"{fixture}: its bytes no longer match the fingerprint they were promoted with; "
                "a promoted fixture is a frozen reproduction, so re-promote it rather than editing it"
            )
        return scenario


def write_scenario(scenario: Scenario, store: Path) -> Path:
    """Write ``scenario`` as ``<store>/<id>/`` with ``<id>.provenance.json`` beside it.

    The provenance file sits beside the tree, never in it, so materialising the tree into a
    workspace hands the agent the scenario's files and nothing about how they were made.

    Every xdist worker collects, so several processes write the same scenario at once. The
    write is therefore idempotent and atomic: a stored copy whose provenance carries this
    fingerprint is left alone, and a new one is staged under a process-unique name and
    renamed into place, so no reader ever sees a half-written tree. The provenance file is
    renamed last, which makes it the marker that the tree beside it is complete.
    """
    tree = store / scenario.id
    meta = tree.with_name(tree.name + PROVENANCE_SUFFIX)
    if tree.is_dir() and meta.is_file() and _stored_fingerprint(meta) == scenario.fingerprint:
        return tree
    unique = f"{os.getpid()}.{uuid.uuid4().hex[:8]}"
    staged = store / f".{scenario.id}.{unique}"
    scenario.write(staged)
    if tree.is_dir():
        # A tree with no provenance is a crashed earlier write, never complete. Otherwise:
        # same id, new bytes: a seed file the generator reads was edited. The records keep
        # the fingerprint they ran with, so the Analyzer never pools the two (ADR 0074).
        stale = store / f".{scenario.id}.stale.{unique}"
        try:
            tree.rename(stale)
        except FileNotFoundError:
            pass  # another worker moved it aside first; the rename below races it fairly
        else:
            shutil.rmtree(stale)
    try:
        staged.rename(tree)
    except OSError:
        # Another worker renamed its identical copy into place first; keep that one.
        if not tree.is_dir():
            raise
        shutil.rmtree(staged)
    staged_meta = staged.with_name(staged.name + PROVENANCE_SUFFIX)
    staged_meta.write_text(json.dumps(scenario.provenance(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    staged_meta.replace(meta)
    return tree


def _stored_fingerprint(meta: Path) -> str | None:
    """The fingerprint a stored scenario's provenance records."""
    found = json.loads(meta.read_text(encoding="utf-8")).get("fingerprint")
    return str(found) if found else None


def stored_scenarios(store: Path) -> dict[str, Path]:
    """Every scenario directory under ``store`` that has its provenance beside it, by id."""
    if not store.is_dir():
        return {}
    return {
        meta.name.removesuffix(PROVENANCE_SUFFIX): meta.with_name(meta.name.removesuffix(PROVENANCE_SUFFIX))
        for meta in sorted(store.glob(f"*{PROVENANCE_SUFFIX}"))
        if meta.with_name(meta.name.removesuffix(PROVENANCE_SUFFIX)).is_dir()
    }


@dataclass(frozen=True, slots=True, kw_only=True)
class GenerationContext:
    """What collection hands a generator: where the suite lives, and how its scenarios fared.

    ``outcomes`` maps a scenario id to ``(failed, sampled)`` over every stored record of the
    case, so an adversarial generator can spend its budget where the subject already breaks.
    ``stored`` maps a scenario id to the directory collection wrote it to, so a past scenario
    can be re-run from its bytes after the generator that made it has moved on.
    """

    evals_dir: Path
    case: str
    outcomes: Mapping[str, tuple[int, int]] = field(default_factory=dict)
    stored: Mapping[str, Path] = field(default_factory=dict)


@runtime_checkable
class FixtureGenerator(Protocol):
    """Anything with a ``name`` and a ``may_be_empty`` flag that yields scenarios, as ``@evalcase(fixture=)`` takes.

    ``may_be_empty`` is declared, never defaulted: True only for a generator whose empty
    sweep is an answer (a regression case before its first promotion, an exhausted search),
    so collection warns by name; False stops collection on an empty sweep (ADR 0074). The
    protocol is runtime-checkable, so a class that omits the flag is refused by ``@evalcase``.
    """

    name: str
    may_be_empty: ClassVar[bool]

    def scenarios(self, context: GenerationContext) -> Iterable[Scenario]:
        """The scenarios to run this sweep, in a stable order."""
        ...
