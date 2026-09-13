# tools

The scripts that produced every number in [../README.md](../README.md), [../scorecard.md](../scorecard.md) and [../scorecard-webapp.md](../scorecard-webapp.md).

They live here rather than in `.claude/skills/lsp/` so this work can be re-run without editing the skill.

`lsp.py` is a fork, taken on 2026-09-11; the original is still where it was.

## Prerequisites

```bash
uv tool install pyright                       # Python: the language server
bun add -g typescript-language-server typescript   # TypeScript: the language server
```

`sqlite-muninn` needs a Python built with loadable SQLite extensions.
The system Python on macOS is not, so pass `--python 3.13` to select a `uv`-managed build.

## The pipeline

```bash
# 1. Extract a call graph. The LSP root must be the project root, not the
#    directory being walked, or the server resolves fewer imports.
uv run --with "lsprotocol>=2024.0.0" tools/callgraph.py \
    src/pytest_xharness_eval tmp/conductance/callgraph.json --lang python --ext .py

uv run --with "lsprotocol>=2024.0.0" tools/callgraph.py \
    report-ui/src tmp/conductance/callgraph-ts.json \
    --lang typescript --ext .ts,.tsx --root report-ui --exclude "__tests__,.test."

# 2. Conductance and leverage, per layer and per file.
uv run tools/score.py --graph tmp/conductance/callgraph.json

# 3. Leiden communities, PageRank, declared against discovered.
uv run --python 3.13 tools/communities.py --graph tmp/conductance/callgraph.json

# 4. The two-part code in bits, for five candidate partitions.
uv run --python 3.13 tools/mdl.py --graph tmp/conductance/callgraph.json
```

`--prefix ts-` on steps 2 to 4 keeps the TypeScript outputs from overwriting the Python ones.

## What each file is

| Script | Purpose |
|---|---|
| `lsp.py` | the amended fork of the skill's indexer. Its docstring lists every amendment and the failure each one was hiding. Read that before changing anything here |
| `callgraph.py` | the standalone extractor used for the documents. Imports `lsp.py` as a library |
| `score.py` | conductance per cluster, leverage per name |
| `communities.py` | `graph_leiden` and `graph_pagerank` through `sqlite-muninn`, and the residual comparison |
| `mdl.py` | `L(H) + L(D given H)` in bits, and bits saved per boundary |
| `bench.py` | three conductance implementations timed against each other at increasing graph size |
| `validate_muninn.py` | cross-checks our Python conductance against `sqlite-muninn` 0.6.0 |
| `weighted.py` | whether counting call sites rather than distinct callers changes the verdict |
| `treesitter.py` | the second extractor: parses source directly, resolves by name, carries the full boundary nesting |
| `levels.py` | conductance at every boundary level, language through class |
| `compare.py` | edge-by-edge diff of two extractions of the same code |

## Two ways to run the indexer

`lsp.py` keeps the skill's full CLI and adds call edges.

```bash
# Build an index with real call edges. Note --lsp-root.
uv run --with "lsprotocol>=2024.0.0" tools/lsp.py index \
    --root src/pytest_xharness_eval --lsp-root . \
    --db-path tmp/conductance/fork_index.db --pretty

# Leverage, both readings, straight out of SQL.
sqlite3 -column tmp/conductance/fork_index.db \
  "SELECT name, callers, call_sites FROM leverage WHERE callers > 0 ORDER BY callers DESC LIMIT 10;"
```

On `src/pytest_xharness_eval` that reports **380 call edges and 515 call sites**.
That matches `callgraph.py` exactly.
If it reports zero edges it now says so loudly rather than exiting 0.

## Three traps that cost real time

- **`--lsp-root` is not `--root`.** Point the server below the project root and pyright resolves fewer imports: 189 edges instead of 380. `typescript-language-server` refuses to start at all, because it resolves `tsserver` from the workspace root.
- **Every document must stay open.** A server asked about a position in a closed file answers with an empty result rather than an error.
- **A parameter is a definition on the same line as its function.** Matching a caller by line alone returns the parameter, which silently halves the edge count.

## What this cannot see

Dynamic dispatch, decorator and plugin registries, and anything reached by reflection.
Treat every graph these produce as a lower bound rather than a census.
Read [../README.md](../README.md), "What we still cannot extract", before trusting a score.

## The second extractor: tree-sitter

`treesitter.py` parses source directly, with no language server.

```bash
uv run tools/treesitter.py src/pytest_xharness_eval --out tmp/conductance/ts-py.json
uv run tools/treesitter.py report-ui/src --out tmp/conductance/ts-ui.json --exclude "__tests__,.test."
uv run tools/treesitter.py src/pytest_xharness_eval report-ui/src --out tmp/conductance/ts-all.json --exclude "__tests__,.test."

uv run tools/levels.py tmp/conductance/ts-all.json     # conductance at every boundary
uv run tools/compare.py tmp/conductance/callgraph.json tmp/conductance/ts-py.json
```

It resolves calls by **name**, not by type, so it trades precision for reach.
Two rules keep the guessing honest.

- A call with a receiver (`x.foo()`) may only match a definition inside a class, and a bare call only one outside. Without that rule every `d.get(k)` on a dict resolved to the module-level `get` in `harness/base.py`.
- Resolution never crosses a language. A Python `of` and a TypeScript `of` share a name and nothing else.

## The two extractors disagree, and that is the finding

Measured on this repository, LSP against tree-sitter:

| | LSP edges | tree-sitter edges | agreed | tree-sitter precision | tree-sitter recall |
|---|---|---|---|---|---|
| Python | 380 | 225 | 207 | 92% | 54% |
| TypeScript | 247 | 542 | 246 | 45% | **100%** |

On Python the LSP wins, because pyright resolves types and tree-sitter cannot.
On TypeScript tree-sitter finds every edge the LSP found, and 296 more.
That is the first real explanation for the 57% orphan rate in `scorecard-webapp.md`.

Neither is ground truth and they agree on about half the union.
Use both and read the disagreement.
