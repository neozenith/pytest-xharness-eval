# tools

**Status:** the working set for [OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md). **Before you start:** `uv` and `bun`.

Five scripts remain here: two call-graph extractors, the diff between them, and the graph reviewable-ui renders.
Every other script that produced a number in [../README.md](../README.md) is archived in git, listed under [Archived scripts](#archived-scripts).

| Script | Purpose |
|---|---|
| `graphdata.py` | emits `reviewable-ui/public/graph.json`, run by `make reviewable-data`. Its shape is mirrored in `reviewable-ui/src/lib/types.ts` |
| `treesitter.py` | extractor that parses source directly and resolves calls by name, in any language with a grammar |
| `callgraph.py` | extractor that asks a language server for `callHierarchy`, resolving calls by type |
| `lsp.py` | the amended fork of the lsp skill's indexer that `callgraph.py` imports. Its docstring lists every amendment and the failure each one was hiding |
| `compare.py` | edge-by-edge diff of an LSP extraction against a tree-sitter extraction of the same code |

---

## Prerequisites

```bash
uv tool install pyright                            # Python language server
bun add -g typescript-language-server typescript   # TypeScript language server
```

## Extract and compare

```bash
# LSP extraction. The LSP root must be the project root, or the server resolves fewer imports.
uv run --with "lsprotocol>=2024.0.0" docs/plans/maintainability/tools/callgraph.py \
    src/pytest_xharness_eval tmp/conductance/callgraph.json --lang python --ext .py

# tree-sitter extraction of the same code.
uv run docs/plans/maintainability/tools/treesitter.py src/pytest_xharness_eval --out tmp/conductance/ts-py.json

# Where the two disagree.
uv run docs/plans/maintainability/tools/compare.py tmp/conductance/callgraph.json tmp/conductance/ts-py.json
```

For TypeScript, pass `--lang typescript --ext .ts,.tsx --root report-ui --exclude "__tests__,.test."` to `callgraph.py`, and `--exclude "__tests__,.test."` to `treesitter.py`.

## Traps that cost real time

- **`--lsp-root` is not `--root`.** Point pyright below the project root and it finds 189 edges instead of 380. `typescript-language-server` refuses to start at all.
- **Every document must stay open.** A server asked about a position in a closed file answers with an empty result rather than an error.
- **A parameter is a definition on the same line as its function.** Matching a caller by line alone returns the parameter.
- **A call with a receiver matches only a method.** Without that rule in `treesitter.py`, every `d.get(k)` resolved to a module-level `get`.
- **Resolution never crosses a language.** A Python `of` and a TypeScript `of` share a name and nothing else.

Every graph these produce is a lower bound.
Read [What we still cannot extract](../README.md#what-we-still-cannot-extract) before trusting a score.

## Archived scripts

The rearrangement sweeps, benchmarks and per-metric scorers were one-off instruments for documents now consolidated into [../README.md](../README.md).

```bash
git ls-tree --name-only 4e4be2e docs/plans/maintainability/tools/      # the full set
git checkout 4e4be2e -- docs/plans/maintainability/tools/<script>.py    # restore one
```

| Script | Produced |
|---|---|
| `score.py`, `levels.py` | conductance and leverage per layer, and inside share per boundary level |
| `communities.py`, `mdl.py` | Leiden communities, and the two-part code in bits per boundary |
| `bench.py`, `validate_muninn.py`, `weighted.py` | the `sqlite-muninn` cross-check, timing, and call-site weighting |
| `experiment.py`, `sweep.py`, `capacity.py` | the rearrangement sweeps and modularity margins |
| `classic.py`, `halstead.py` | the blind-spots table for cyclomatic, cognitive and Halstead metrics |
| `tsview.py` | the tree-sitter file view, superseded by reviewable-ui |
