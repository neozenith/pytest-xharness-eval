# 0039: The package listing is the architecture

Status: accepted, 2026-08-28. Refines
[0014](0014-register-through-the-pytest11-entry-point.md) (register through the
pytest11 entry point),
[0027](0027-coverage-follows-the-shells-working-directory.md) (coverage follows
the shell's working directory),
[0034](0034-a-harness-is-a-class-and-the-registry-is-the-only-dispatch.md) (a
harness is a class and the registry is the only dispatch) and
[0037](0037-the-emitted-records-are-types-and-the-cache-tree-has-one-owner.md)
(the emitted records are types). Structural only: no serialised key, no ini key,
no CLI option and no metric's value changes, and the characterization goldens are
byte-identical.

## Context

Twenty modules sat flat in `src/pytest_xharness_eval/`, in one alphabetical list,
after 0034 pulled `harness/` out of it. A reader opening the package could not
tell from the listing that `case.py` is a declaration a user writes, `codex.py`
folds a foreign log, `pricing.py` is arithmetic over a folded one, `report.py`
publishes, and `plugin.py` drives all four — they are the same size, at the same
level, in the same column. The listing named the parts and said nothing about
the shape, which is the complaint this refactoring campaign opened with.

Flatness is not only a reading problem: with no declared direction, three
imports had quietly turned upside down, and nothing failed when they did.

| Inversion | What it meant |
| --- | --- |
| `pricing` → `normalise.now_iso`, `report` → `normalise.now_iso` | Pricing an estimate and stamping an index both depended on the *harness dialect toolkit* for a wall clock. |
| `skillcov.annotate` → `harness.get(result.harness)` | A derivation reached into the adapter registry mid-walk, so annotating a ledger — pure arithmetic — could not be done for a result whose harness nobody had registered. |
| `matrix` → `harness` | Deliberate and correct (the `--harness` choices must be whatever is registered, 0034), but indistinguishable from the other two. |

Two names in the package are resolved by *importlib*, not by Python code, and
they bound any re-layering: `pytest_xharness_eval.plugin` is the `pytest11`
entry point (0014) and `pytest_xharness_eval.replay` is what
`uv run -m pytest_xharness_eval.replay` executes. Verified: a package with no
`__main__.py` fails `-m` outright, and an attribute re-exported from a parent
`__init__` does not satisfy importlib for either — only a real module does.

## Decision

**The layers are folders, and the folder listing is the dependency order.**

```text
pytest_xharness_eval/
    plugin.py     the pytest11 entry point (0014)
    replay.py     the `python -m` entry point (0023, 0032)
    model/        the nouns: run, case, cell, workspace, cache tree, clock
    harness/      one adapter class per agent CLI, and the toolkit they fold with
    derive/       what a folded run cost, and which of the skill it reached
    emit/         the documents that leave: the metrics record and the microsite
    runtime/      how a sweep is wired: settings, and the steps after the CLI returns
```

Each layer depends only on the ones above it in that list, entry points last.
The two entry-point modules stay real modules at the root because importlib
resolves them, and that placement narrates too: what the outside world calls at
the top, the layers it calls through underneath.

**Each `__init__` declares its layer's surface.** A layer's `__init__` is the
one place its public names are listed, and reading five of them is reading the
architecture. Submodules still import each other by full dotted path
(`from pytest_xharness_eval.derive import pricing`), never through a layer's
`__init__`: importing the matrix reaches the harness registry, so a name bound
in an `__init__` is not yet available to everything that loads during it.

**The three inversions are resolved, not merely noted.** `now_iso` and
`ms_between` are `model/clock.py`, a leaf that depends on nothing, so pricing and
the report stop naming the adapter toolkit for a timestamp; the tolerant reader
for this package's own stored documents is `model/documents.py` for the same
reason. `skillcov.annotate` takes the harness's shell vocabulary as an optional
fourth argument — a `model.registry.Shells` value of the tool names that run a
shell and the ones that keep their cwd (0027) — so annotating a ledger is
arithmetic over a value it was handed. And the one edge that must point up,
because the registry is the only dispatch (0034), is now a single module that
says so: `model/registry.py` answers "which harnesses exist" and "what is this
one's shell vocabulary", and it is the only module below `harness/` that names
`harness`. `annotate` still resolves through it when the argument is omitted,
which is what the pipeline and the pinned characterization call.

**A fourth inversion fails the build.** The ruff `TID251` rule that has kept
provider modules unreachable since 0034 is joined by three more: nothing may name
`pytest_xharness_eval.harness`, `.emit` or `.runtime` except the layers above it,
and the exceptions are the per-file-ignore list in `pyproject.toml` — the two
entry points, each layer itself, `model/registry.py`, and the tests.

**`report.py` becomes the layer it always was.** It held four jobs at once: the
`index.json` row type, the design-tokens reader, the page assembly, and the
combine step. They are `emit/index.py`, `emit/tokens.py` and `emit/page.py`
beside `emit/metrics.py`, which is the same split the microsite already has on
disk. `pytest_xharness_eval.emit` is re-exported from the root package as
`report`, which is the name `report-ui/scripts/inline.py` builds a page through.

## Consequences

`import pytest_xharness_eval.pricing` — the dotted form — stops resolving for an
outside caller. The from-import form `from pytest_xharness_eval import pricing`
still does, and so do `normalise`, `records`, `skillcov` and `report`: they are
re-exported from the root `__init__` in `as` form (mypy's `no_implicit_reexport`
requires it) and listed in `__all__` as the declared public API. Every internal
caller and both test modules use the from-import form, and the pinned
characterization test imports exactly that way, unchanged.

The bundled `prices.toml` moves to `derive/prices.toml`, beside the only module
that reads it. 0014's rule is unchanged: it is still the one path derived from
`__file__`, and `pricing.py` still spells it `Path(__file__).parent`.

`model/` is where `layout.py` and `workspace.py` live, not `runtime/`. Both are
value-level — one names paths under a cache, the other copies a fixture tree and
hashes it — and both are used *by* the harness adapters, so putting them in the
top layer would have made the adapter layer import the top layer and left the
`runtime` ban with a hole big enough to walk through.

One edge points up that the rules cannot express: `model/runresult.py` names
`derive.pricing` and `derive.skillcov` under `TYPE_CHECKING`, to declare the two
derived documents a result carries. It is annotations only, so there is no
runtime dependency and no cycle, and it is the reason `derive` is not in the ban
list — a rule with a documented exception in the file it exists to constrain is
worse than no rule.

## Lens

A package listing is the first documentation anyone reads and the only one that
cannot go stale. When it is a flat alphabetical column, every module claims equal
standing and the reader learns nothing; when the folders are the layers, the
question "may this import that?" has an answer before the import is written — and
the answer can be checked by a linter rather than by whoever reviews the diff.
The names that resolve outside the language, though, are load-bearing in a way no
layering may break: an entry point is a contract with a tool that does not read
your architecture, and it stays a real module at the root no matter how the rest
is arranged.
