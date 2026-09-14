# tools

**Status:** the working set for [OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md). 

**Before you start:** `uv` and `bun`.

Six scripts remain here: two call-graph extractors, the diff between them, the graph reviewable-ui renders, and the per-function screen load.
Every other script that produced a number in [../README.md](../README.md) is archived in git, listed under [Archived scripts](#archived-scripts).

| Script | Emits | Purpose |
|---|---|---|
| `graphdata.py` | `GR-CON-01`, `GR-VOL-02`, `GR-MOD-03`, `GR-INS-05`, `GR-LEV-06`, `GR-ORP-08`, `GR-FAN-09`, `GR-SIT-10`, `PR-LOC-01`, `TS-NES-06`, `EX-RES-01` | emits `reviewable-ui/public/graph.json`, run by `make reviewable-data`. Its shape is mirrored in `reviewable-ui/src/lib/types.ts` |
| `treesitter.py` | the graph every `GR` metric needs | extractor that parses source directly and resolves calls by name, in any language with a grammar |
| `callgraph.py` | the same graph, resolved by type | extractor that asks a language server for `callHierarchy`, resolving calls by type |
| `lsp.py` | nothing, it is support code | the amended fork of the lsp skill's indexer that `callgraph.py` imports. Its docstring lists every amendment and the failure each one was hiding |
| `compare.py` | `EX-REC-02` | edge-by-edge diff of an LSP extraction against a tree-sitter extraction of the same code |
| `screenload.py` | `TS-SCR-03`, `PR-VIS-02` | per-function [screen load](../GLOSSARY.md#ts-scr-03-screen-load): lines, tokens and distinct names, for V5, C8 and D5. `uv run docs/plans/maintainability/tools/screenload.py --out tmp/screenload.json` |

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
- **`fromRanges` is not deduplicated.** pyright returns the same range twice for one method call, so `len(fromRanges)` overcounts. Measured in [../examples/README.md](../examples/README.md).
- **`CALLABLE_KINDS` misses SymbolKind 14.** `documentSymbol` calls an arrow-function component a Constant while `prepareCallHierarchy` calls it a Function, so every one of them is filtered out.
- **Construction is not a call.** `Greeter("Howdy")` gives `Greeter.__init__` zero incoming calls, so a constructor edge has to come from somewhere else.

Every graph these produce is a lower bound.
Read [What we still cannot extract](../README.md#what-we-still-cannot-extract) before trusting a score.
[extraction-apis.md](../extraction-apis.md) catalogues what each instrument can be asked for in the first place.

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
