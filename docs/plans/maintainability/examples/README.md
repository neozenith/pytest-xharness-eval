# Five providers over one hello world

Two toy codebases, run through every provider in [ast-data-models.md](../ast-data-models.md) that has a runnable extractor.
The point is not the codebases, it is what each provider hands back for the same fifty-three lines.

Both fixtures are built around one deliberate trap.
A name is declared twice, and one call site can only be resolved by knowing a type or walking a scope.
A provider that gets that call right has performed name resolution, and one that guesses has not.

| Provider | State here | How it was run |
|---|---|---|
| tree-sitter | measured | `tools/treesitter.py` over each fixture directory |
| stack-graphs | measured | `tree-sitter-stack-graphs-python` and `-typescript`, built from source with cargo |
| LSP | measured | `pyright` and `typescript-language-server`, driven by `tmp/hello_lsp_probe.py` |
| SCIP | measured | `scip-python@0.6.6` and `scip-typescript@0.4.0`, decoded against `scip.proto` |
| scope-graphs | schema-derived | no packaged indexer exists for Python or TSX, so its ERD comes from the paper |

**Every number below was read off a real run, except where a row says schema-derived.** The scope-graphs entity model is transcribed from the ESOP 2015 paper and the Statix reference.

The LSP rows come from `tmp/hello_lsp_probe.py` rather than from `tools/callgraph.py`.
The probe keeps every field the server sent, and `callgraph.py` folds most of them away before they can be read.

## The Python fixture

[hello-python/](hello-python/) is two files and thirty-one lines.

`greet.py` declares `greet` twice, once as a module-level function and once as a method of `Greeter`.
`main.py` calls the module-level `greet` twice, then calls the method once through `Greeter("Howdy").greet(...)`.

The interesting call site is `main.py:10:28`.
Resolving it to `Greeter.greet` rather than to the module-level `greet` requires a type or a scope.

## The React fixture

[hello-react/](hello-react/) is two TSX files and twenty-two lines, beside a `package.json` and a git-ignored `node_modules`.
The dependency tree is 24 MB of `@types/react` and exists so the providers can resolve JSX at all.

`Greeting.tsx` exports a named function component and an arrow component assigned to a `const`.
`App.tsx` imports both, then uses `<Greeting />` twice and `<Shout />` once.
The import statement is itself a reference, so JSX is the only use of either component but not its only mention.

The interesting question is whether a provider sees `<Greeting />` as a use of `Greeting` at all.
The second question is whether the arrow component survives, because it is a `const` rather than a function.

## What each provider emitted

### tree-sitter

| Fixture | Callables | Edges | Call sites found |
|---|---|---|---|
| hello-python | 4 | 2 | `main -> greet` 2 sites, `main -> Greeter.greet` 1 site |
| hello-react | 3 | 2 | `App -> Greeting` 2 sites, `App -> Shout` 1 site |

Both fixtures reported `resolved: 3, ambiguous: 0, unresolved: 4`.
In Python the four are three `print` calls and `Greeter`, and in React they are `div`, `h1`, `strong` and `toUpperCase`.
None of those is declared inside the fixture, so a name-matching extractor has nothing to match against.

**`Greeter("Howdy")` is unresolved here, and the LSP gives it no call edge either, but not for the same reason.** `treesitter.py` puts `class_definition` in its `classes` set and not its `defs` set, so no `Greeter` callable ever exists.
pyright does build `Greeter.__init__` as SymbolKind 6 and does prepare it, then returns zero incoming calls.
One provider has no node to resolve to, and the other has the node and declines the edge.

The `main()` call at the bottom of `main.py` is not counted at all, because a top-level call has no calling function.
An entry point therefore looks like an orphan to this extractor.

`tools/treesitter.py` routed `Greeter("Howdy").greet(...)` to the method, and it did so from a receiver heuristic rather than a type.
The extractor counts `jsx_opening_element` and `jsx_self_closing_element` as calls, which is why `<Greeting />` became an edge.

**tree-sitter itself resolved nothing.** Every edge above is the extractor's own rule matching over a parse tree, so the correctness belongs to `tools/treesitter.py` and not to the provider.

### stack-graphs

All eight node variants named in [ast-data-models.md](../ast-data-models.md) appear in the thirty-one-line Python fixture.

| Fixture | Nodes | Edges | Variants present |
|---|---|---|---|
| hello-python | 521 | 292 | 386 scope, 64 push, 51 pop, 8 push-scoped, 5 pop-scoped, 5 drop-scopes, root, jump-to-scope |
| hello-react | 699 | 466 | 493 scope, 103 push, 100 pop, 1 push-scoped, root, jump-to-scope |

The TypeScript graph has no `drop_scopes` and no `pop_scoped_symbol`, so the variant set is a property of the rule file rather than the language.
Only two of 292 Python edges carry a non-zero `precedence`, and both run between two scope nodes at `main.py:1:1`.
Precedence is therefore present in the model and barely exercised at this size.

`query definition main.py:10:28` returned exactly one definition, `greet.py:15:9`, which is `Greeter.greet`.
**That is the headline result, because it needed no type inference and no language server.**

`<Greeting />` at `App.tsx:8:8` resolves to two definitions, and so does `<Shout />` at `10:8`.
Each returns the import binding in `App.tsx:3` alongside the real declaration, `Greeting.tsx:3:17` and `Greeting.tsx:7:14`.
JSX element names are reference nodes, and the arrow component is found without a special case.

A caller that wants the declaration has to walk past the import binding, because both arrive as definitions of equal standing.

`source_info.syntax_type` is populated for only five of the fifteen Python definition nodes.
Those five are `function`, `method` and `class`, and every parameter, import alias and module definition carries nothing.
React fills it more often, on eight of nineteen definition nodes, as four `module`, two `function` and two `field`.
On that side `Greeting` is `function` while `Shout` has no `syntax_type` at all, yet both still resolve.

Two reference nodes sit at most Python source positions and a minority of React ones.

| Fixture | Distinct reference positions | One node | Two nodes |
|---|---|---|---|
| hello-python | 23 | 5 | 18 |
| hello-react | 20 | 13 | 7 |

The doubling is an artefact of the rule file rather than an ambiguity, and it is not uniform.
The headline position `main.py:10:28` is one of the singles, which is why its query reports one reference and one definition.

The sqlite layout confirms the incrementality model.

| Table | hello-python | hello-react | What it holds |
|---|---|---|---|
| `graphs` | 2 rows, 101870 and 85539 bytes | 2 rows, 114848 and 165434 bytes | one content-tagged blob per file |
| `file_paths` | 90 rows | 63 rows | partial paths that stay inside one file |
| `root_paths` | 2 rows | 2 rows | partial paths reachable from the root node |

**Neither database is portable, because `graphs.file` and `root_paths.file` are absolute paths in both.** A database built in one checkout will not answer queries in another.

The two languages differ in how deep that goes.
The Python `root_paths` symbol stacks are `V␞greet` and `V␞main`, which are just the two module names.
The TypeScript ones embed the absolute filesystem path inside the symbol stack itself.

### LSP

pyright and `typescript-language-server` both resolved every call correctly, and both misreported something structural.

| Request | Symbol | Result |
|---|---|---|
| `documentSymbol` | `greet.py` | 8 symbols, including three kind 13 parameters and one kind 13 attribute |
| `incomingCalls` | `greet` kind 12 | from `main`, `fromRanges` 2, at `7:10` and `8:10` |
| `incomingCalls` | `greet` kind 6 | from `main`, `fromRanges` 2, **both at `9:27-32`** |
| `incomingCalls` | `__init__` kind 6 | no incoming calls at all |
| `incomingCalls` | `main` kind 12 | from `(module) main.py` kind 2, `fromRanges` 1 |

**pyright emits the same range twice for the single method call site.** `fromRanges` is therefore not deduplicated, and any metric that counts its length overcounts.
`tools/callgraph.py` does count its length, and its own Python run reports two sites on both edges, four for three real calls.

**Construction is not a call.** `Greeter("Howdy")` produced zero incoming calls on `Greeter.__init__`, so a constructor edge has to come from somewhere else.

On the React side the disagreement is about kinds rather than counts.

| Request | `Greeting` | `Shout` |
|---|---|---|
| `documentSymbol` | kind 12, Function | **kind 14, Constant** |
| `prepareCallHierarchy` | kind 12 | **kind 12, Function** |
| `incomingCalls` | from `App`, 2 ranges at `7:7` and `8:7` | from `App`, 1 range at `9:7` |

The two requests describe the same symbol with two different kinds.
`tools/callgraph.py` filters on `CALLABLE_KINDS = {6, 9, 12}` from `documentSymbol`, so a `const`-bound arrow component is invisible to it.
Its `--include-variables` flag was written for exactly this case and adds kind 13, which is Variable.
**A `const` binding is reported as kind 14, so the escape hatch does not reach the symbol it was built for.** The probe hardcodes `{6, 9, 12, 13, 14}`, which is how `Shout` was measured at all.

`<Greeting />` does arrive as an incoming call with two correct ranges, so JSX usage is visible to callHierarchy.

### SCIP

| Fixture | Documents | Occurrences | Symbols | External symbols |
|---|---|---|---|---|
| hello-python | 2 | 22 and 14 | 11 and 2 | 2 |
| hello-react | 2 | 16 and 13 | 7 and 2 | 0 |

The descriptor grammar separates the collision cleanly.
The module function is `…/greet().` and the method is `…/Greeter#greet().`, and the method is referenced exactly once.
**SCIP got the call count right where pyright double-counted it.**

The two React definition shapes are distinguishable from the symbol string alone.
`Greeting` is `…/Greeting().` with the method suffix, and `Shout` is `…/Shout.` with the plain term suffix.

Cross-package resolution works without the package being indexed.
`<div>` resolves to ``scip-typescript npm @types/react 19.3.0 `index.d.ts`/React/JSX/IntrinsicElements#div.``, and `print` resolves to `scip-python python python-stdlib 3.11 builtins/print().`.

Three schema fields are declared and left empty by both indexers.

- `Document.language` is `""`.
- `SymbolInformation.kind` is `0`.
- `display_name` is `""`.

**The two indexers disagree about `symbol_roles` on references.** scip-typescript leaves it `0` while scip-python writes `ReadAccess`, and `SymbolRole` has no member that means "call".

The Python import does not join up.
The module reference at range `[2, 5, 10]` resolves to `scip-python python hello-python 0.0.0 greet/__init__:`, while the definitions live under `` `docs.plans.maintainability.examples.hello-python.greet` ``.
That is one module under two spellings, and the fixture has no package root to reconcile them.

The `Import` role is never set either.
Every reference in the import statement carries `ReadAccess`, so an import is indistinguishable from a use.

### scope-graphs

No packaged scope graph indexer exists for Python or TSX, so nothing was measured.
The formalism is realised in Statix and in the stack-graphs line of work, and the second of those is measured above.

**Read the stack-graphs rows as the closest available evidence for what a scope graph yields.** The eight node variants carry the paper's three entities and two edge labels.
The 90 `file_paths` rows are its intra-file resolution paths, made incremental.

## What the fixtures actually settled

**Only stack-graphs and SCIP resolved the name collision from stored data alone.** tree-sitter needed a receiver heuristic written into the extractor, and LSP needed a running type checker.

**JSX usage is visible to four of the five providers.** tree-sitter counts the element, stack-graphs makes the element name a reference, LSP reports it through callHierarchy, and SCIP records it as an occurrence.
Only tree-sitter calls it a call, because SCIP has no call role and the other two report a reference or a hierarchy edge.

**Two real defects came out of this, one in `tools/` and one in pyright.** `--include-variables` adds SymbolKind 13 where a `const`-bound component needs 14, and pyright duplicates a `fromRanges` entry for a single call site.

**A provider that populates a field is not a provider that populates it everywhere.**

- `syntax_type` covers five of the fifteen Python definitions and eight of the nineteen React ones.
- `definiens_span` and `fully_qualified_name` are declared in the stack-graphs ERD and never written in either fixture.
- `symbol_roles` differs between the two SCIP indexers.
- `kind` and `display_name` are empty in both of them.

## Reproducing this

Every command below runs from the repository root.
The stack-graphs binaries are not published, so both were built with `cargo install` into a project-local root and are reached by `PATH`.

```bash
export PATH="$PWD/tmp/cargo/bin:$PWD/tmp/cargo-ts/bin:$PATH"
FIXTURE=docs/plans/maintainability/examples/hello-python

# tree-sitter.
uv run docs/plans/maintainability/tools/treesitter.py "$FIXTURE" --out tmp/hello/ts-python.json

# LSP. The probe keeps every field; callgraph.py folds them away.
uv run tmp/hello_lsp_probe.py "$FIXTURE" tmp/hello/lsp-raw-python.json --lang python --ext .py

# SCIP. Both paths must be absolute, and the output file must already exist.
bunx @sourcegraph/scip-python index --cwd "$PWD/$FIXTURE" --output "$PWD/tmp/hello/scip/python.scip"
uv run tmp/scip_dump.py tmp/hello/scip/python.scip tmp/hello/proto/scip.proto tmp/hello/scip-python.json

# stack-graphs. `index` writes only the database, so `visualize` is a second pass.
tree-sitter-stack-graphs-python index -D tmp/hello/sg/python.sqlite "$FIXTURE"
tree-sitter-stack-graphs-python visualize -D tmp/hello/sg/python.sqlite -o tmp/hello/sg/python.html "$FIXTURE"
tree-sitter-stack-graphs-python query -D tmp/hello/sg/python.sqlite definition "$FIXTURE/main.py:10:28"

# The node, edge and reference censuses read the visualisation, not the database.
uv run tmp/sg_census.py tmp/hello/sg/python.html
uv run tmp/audit/ref_positions.py tmp/hello/sg/python.html
```

The React fixture is the same sequence with `scip-typescript`, the `-typescript` binary and the react paths.
`treesitter.py` needs no language flag, because it picks a grammar per file extension.
`callgraph.py` and the probe both take `--lang typescript --ext .tsx`, but `callgraph.py` defaults its LSP root to the repository rather than the fixture.

**Do not run `scip-python` without `--cwd`.** It walks up to the repository's own `pyproject.toml` and indexes the whole tree instead of the fixture.
