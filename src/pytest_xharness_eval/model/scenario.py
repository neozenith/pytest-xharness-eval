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

#: The params key an adversarial mutant records its parent and mutators under (ADR 0074).
MUTATION_KEY: Final = "mutation"

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

    def provenance(self) -> Provenance:
        """What a stored or promoted copy of this scenario keeps beside its bytes."""
        return Provenance(
            generator=self.generator,
            version=self.version,
            id=self.id,
            label=self.label,
            params=dict(self.params),
            expect=dict(self.expect),
            task=self.task,
            fingerprint=self.fingerprint,
        )

    @classmethod
    def promoted(cls, fixture: Path) -> Self:
        """The scenario a stored or promoted fixture directory holds, read with its provenance file."""
        meta = Provenance.read(fixture)
        scenario = cls(
            generator=meta.generator,
            version=meta.version,
            params=dict(meta.params),
            files=read_tree(fixture),
            label=meta.label,
            task=meta.task,
            expect=dict(meta.expect),
        )
        if scenario.fingerprint != meta.fingerprint:
            raise ValueError(
                f"{fixture}: its bytes no longer match the fingerprint they were promoted with; "
                "a promoted fixture is a frozen reproduction, so re-promote it rather than editing it"
            )
        return scenario


@dataclass(frozen=True, slots=True, kw_only=True)
class Provenance:
    """How a stored scenario was made: the ``<id>.provenance.json`` beside its tree, never inside it.

    One type for the store collection writes, the history an adversary reads back, and the
    committed fixture promotion freezes. ``promoted_from`` names the session a promoted copy
    came from, and is absent (None, and no key) on a scenario that was only stored.
    """

    generator: str
    version: int
    id: str
    label: str | None
    params: Mapping[str, Any]
    expect: Mapping[str, Any]
    task: str | None
    fingerprint: str
    promoted_from: Mapping[str, Any] | None = None

    @staticmethod
    def path_for(tree: Path) -> Path:
        """Where the provenance of the scenario tree ``tree`` lives: beside it."""
        return tree.with_name(tree.name + PROVENANCE_SUFFIX)

    @property
    def parent(self) -> str | None:
        """The scenario an adversarial mutant was bred from, None for anything else (ADR 0074)."""
        mutation = self.params.get(MUTATION_KEY)
        parent = mutation.get("parent") if isinstance(mutation, dict) else None
        return parent if isinstance(parent, str) else None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "generator": self.generator,
            "version": self.version,
            "id": self.id,
            "label": self.label,
            "params": dict(self.params),
            "expect": dict(self.expect),
            "task": self.task,
            "fingerprint": self.fingerprint,
        }
        if self.promoted_from is not None:
            out["promoted_from"] = dict(self.promoted_from)
        return out

    @classmethod
    def read(cls, tree: Path) -> Self:
        """The provenance beside ``tree``."""
        meta = json.loads(cls.path_for(tree).read_text(encoding="utf-8"))
        promoted = meta.get("promoted_from")
        return cls(
            generator=str(meta["generator"]),
            version=int(meta["version"]),
            id=str(meta.get("id") or tree.name),
            label=meta.get("label"),
            params=dict(meta["params"]),
            expect=dict(meta.get("expect") or {}),
            task=meta.get("task"),
            fingerprint=str(meta["fingerprint"]),
            promoted_from=dict(promoted) if isinstance(promoted, dict) else None,
        )

    def write(self, path: Path) -> Path:
        """Write this record to ``path`` as indented, sorted JSON."""
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path


@dataclass(frozen=True, slots=True)
class ScenarioStore:
    """A directory of scenario trees, each with its :class:`Provenance` beside it.

    ``<cache>/scenarios/<suite path>/<case>/`` is one (``CacheLayout.scenario_store``), and so
    is a suite's ``evals/fixtures/`` once a failure has been promoted into it. Every reader
    and writer of the layout goes through here, so the file names have one owner.
    """

    root: Path

    def tree(self, scenario_id: str) -> Path:
        """Where the scenario ``scenario_id`` is, or would be, stored."""
        return self.root / scenario_id

    def write(self, scenario: Scenario) -> Path:
        """Write ``scenario`` as ``<root>/<id>/`` with ``<id>.provenance.json`` beside it.

        The provenance file sits beside the tree, never in it, so materialising the tree into
        a workspace hands the agent the scenario's files and nothing about how they were made.

        Every xdist worker collects, so several processes write the same scenario at once. The
        write is therefore idempotent and atomic: a stored copy whose provenance carries this
        fingerprint is left alone, and a new one is staged under a process-unique name and
        renamed into place, so no reader ever sees a half-written tree. The provenance file is
        renamed last, which makes it the marker that the tree beside it is complete.
        """
        tree = self.tree(scenario.id)
        meta = Provenance.path_for(tree)
        if tree.is_dir() and meta.is_file() and Provenance.read(tree).fingerprint == scenario.fingerprint:
            return tree
        unique = f"{os.getpid()}.{uuid.uuid4().hex[:8]}"
        staged = self.root / f".{scenario.id}.{unique}"
        scenario.write(staged)
        if tree.is_dir():
            # A tree with no provenance is a crashed earlier write, never complete. Otherwise:
            # same id, new bytes: a seed file the generator reads was edited. The records keep
            # the fingerprint they ran with, so the Analyzer never pools the two (ADR 0074).
            stale = self.root / f".{scenario.id}.stale.{unique}"
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
        scenario.provenance().write(Provenance.path_for(staged)).replace(meta)
        return tree

    def stored(self) -> dict[str, Path]:
        """Every scenario tree under the store that has its provenance beside it, by id."""
        if not self.root.is_dir():
            return {}
        trees = (
            meta.with_name(meta.name.removesuffix(PROVENANCE_SUFFIX))
            for meta in sorted(self.root.glob(f"*{PROVENANCE_SUFFIX}"))
        )
        return {tree.name: tree for tree in trees if tree.is_dir()}

    def provenance(self, scenario_id: str) -> Provenance:
        """The provenance of the stored scenario ``scenario_id``."""
        return Provenance.read(self.tree(scenario_id))

    def lineage(self) -> dict[str, str]:
        """Each stored adversarial mutant's id, mapped to the id of the scenario it was bred from."""
        out: dict[str, str] = {}
        for sid in self.stored():
            parent = self.provenance(sid).parent
            if parent is not None:
                out[sid] = parent
        return out


def write_scenario(scenario: Scenario, store: Path) -> Path:
    """``ScenarioStore(store).write(scenario)``: the scenario's tree, with its provenance beside it."""
    return ScenarioStore(store).write(scenario)


def stored_scenarios(store: Path) -> dict[str, Path]:
    """``ScenarioStore(store).stored()``: every complete scenario tree under ``store``, by id."""
    return ScenarioStore(store).stored()


@dataclass(frozen=True, slots=True, kw_only=True)
class GenerationContext:
    """What collection hands a generator: where the suite lives, and how its scenarios fared.

    ``outcomes`` maps a scenario id to ``(failed, sampled)`` over every stored record of the
    case, so an adversarial generator can spend its budget where the subject already breaks.
    ``store`` is where collection writes the case's scenarios, so a past scenario can be re-run
    from its bytes after the generator that made it has moved on; None for a generator asked
    outside a sweep, which then sees no history.
    """

    evals_dir: Path
    case: str
    outcomes: Mapping[str, tuple[int, int]] = field(default_factory=dict)
    store: ScenarioStore | None = None

    @property
    def stored(self) -> dict[str, Path]:
        """Every complete scenario tree in the case's store, by id; empty without a store."""
        return self.store.stored() if self.store is not None else {}


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
