# hello-python, as five providers see it

Every graph on this page is drawn from what a provider actually emitted for [hello-python/](hello-python/).
The numbers behind them are in [README.md](README.md), and this page is the picture of the same runs.

The graphs are data-driven blocks for the `richdocs` viewer, so on GitHub each one shows only a pointer to its JSON.
Render the page with the commands in [Rebuilding this page](#rebuilding-this-page) to see them.

---

<details>
<summary><b>Table of Contents</b></summary>
<!--TOC-->

- [hello-python, as five providers see it](#hello-python-as-five-providers-see-it)
  - [The fixture](#the-fixture)
  - [How much each provider hands back](#how-much-each-provider-hands-back)
  - [tree-sitter: a tree, and a call graph built on it by hand](#tree-sitter-a-tree-and-a-call-graph-built-on-it-by-hand)
  - [stack-graphs: every reference joined to its definitions](#stack-graphs-every-reference-joined-to-its-definitions)
  - [LSP: symbols per file, and calls between them](#lsp-symbols-per-file-and-calls-between-them)
  - [SCIP: occurrences pointing at symbol strings](#scip-occurrences-pointing-at-symbol-strings)
  - [scope-graphs: drawn by hand from the paper](#scope-graphs-drawn-by-hand-from-the-paper)
  - [What the pictures show side by side](#what-the-pictures-show-side-by-side)
  - [Rebuilding this page](#rebuilding-this-page)

<!--TOC-->
</details>

---

## The fixture

Two files and thirty-one lines, built around one name declared twice.

```python
# greet.py
def greet(name: str) -> str:
    return f"Hello, {name}!"


class Greeter:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def greet(self, name: str) -> str:
        return f"{self.prefix}, {name}!"
```

```python
# main.py
from greet import Greeter, greet


def main() -> None:
    print(greet("world"))
    print(greet("again"))
    print(Greeter("Howdy").greet("world"))


if __name__ == "__main__":
    main()
```

Docstrings are omitted above, so line numbers on this page refer to the files on disk.
The call that matters is `.greet` at `main.py:10:28`, which only a type or a scope rule can send to the method.

---

## How much each provider hands back

The same thirty-one lines produce anything from two call edges to 521 graph nodes.

```plotly
{ "data": "graphs/hello-python-sizes.json" }
```

**Size is not information.** The two call edges from `treesitter.py` and the 521 stack-graphs nodes describe the same three call sites.
Most stack-graphs nodes are scopes that exist to make resolution a path search, and the next sections show what they buy.

---

## tree-sitter: a tree, and a call graph built on it by hand

### The syntax tree of main.py

tree-sitter emits a tree of typed byte ranges and nothing else.
The graph shows only named nodes, and the shaded ones are leaves, labelled with their source text.

```cytoscape
{ "data": "graphs/hello-python-ts-cst.json" }
```

Nothing in the tree says that `greet` inside `main` is the function in `greet.py`.
Every `identifier` is just text at a position.

### What tools/treesitter.py builds from it

The extractor matches call nodes to definition nodes by name, with one rule that a call through a receiver may only match a method.

```cytoscape
{ "data": "graphs/hello-python-ts-callgraph.json" }
```

**The method edge is right for the wrong reason.** `Greeter("Howdy").greet` reaches `Greeter.greet` because it has a receiver, not because anything knew its type.

**The class and the entry point fall out.** `Greeter` has no callable node, so its construction has no match.
The `main()` call on line 14 sits outside every function, so it has no caller and is dropped.

---

## stack-graphs: every reference joined to its definitions

### Node variants

All eight node variants appear, and scope nodes are three quarters of them.

```plotly
{ "data": "graphs/hello-python-sg-variants.json" }
```

### Which definition each reference reaches

Each arrow is an answer from the stack-graphs CLI itself, asked about every reference to a callable or class name.
Push nodes are references, and the shaded pop nodes are definitions.

```cytoscape
{ "data": "graphs/hello-python-sg-references.json" }
```

**The method call resolves to exactly one definition**, `greet.py:15:9`, with no type checker involved.
The two plain calls on lines 8 and 9 each reach two definitions: the import binding on line 3, and the function in `greet.py`.

**A reference is not a caller.** stack-graphs joins a position to a definition, and never says which function the position sits inside.
A call graph still needs the syntax tree to name the caller.

### One resolution, step by step

This is the path from `main.py:10:28` to `greet.py:15:9`, replayed over the emitted graph with the symbol-stack and scope-stack rules.
The generator refuses to draw it unless the replay reaches the same definitions the CLI reports.
Runs of the same node type are folded, so 39 graph nodes become 24 steps.
Each step shows the symbol stack after it, with the top on the right.

```cytoscape
{ "data": "graphs/hello-python-sg-path.json" }
```

**The type inference is a symbol.** The reference pushes `greet`, then `.`, then a scoped `()` standing for "the result of calling", then `Greeter`.
In `main.py` the import binding pops `Greeter` and pushes it again, qualified by its module as `greet . Greeter`.
The path crosses the shared root, and `greet.py` pops the module name and its `.` before the class pops `Greeter`.
Popping the scoped `()` restores the scopes it carried, `drop_scopes` discards them, and an ordinary edge leads into the class members.
Only then can `.` and `greet` pop, and the stack reaches empty at the method.

That is how a rule file written against syntax alone resolves a method call a name matcher can only guess.

---

## LSP: symbols per file, and calls between them

Each box inside a file is a `documentSymbol` result, labelled with its `SymbolKind`.
A box that appears only as a caller, such as a module, comes from `incomingCalls` instead.
Shaded boxes were also answered by `prepareCallHierarchy`, and each arrow is one `callHierarchy/incomingCalls` item with its `fromRanges`.

```cytoscape
{ "data": "graphs/hello-python-lsp.json" }
```

**The method edge carries `10:28` twice.** pyright repeats the range for a single call site, so counting `fromRanges` makes one call look like two.

**`Greeter.__init__` has no arrow at all.** It was prepared as a Method, and pyright returned no incoming call for `Greeter("Howdy")`.

**The entry point has a caller the other providers lack.** `main` is called from a node pyright names after the module, because the call on line 14 sits at module level.

---

## SCIP: occurrences pointing at symbol strings

Every occurrence in each document points at the symbol string it names.
Each occurrence is labelled with its document, position and roles, and solid arrows mark definitions.

```cytoscape
{ "data": "graphs/hello-python-scip.json" }
```

**The collision is two different strings.** `greet().` and `Greeter#greet().` never meet, so the method is referenced exactly once.

**Every reference is `ReadAccess`, including the imports.** A call, a type annotation and an import all carry the same role.

**One module has two spellings.** The import on line 3 points at `greet/__init__:`, filed under symbols from elsewhere, while its definitions live under the backticked dotted path.
The fixture has no package root to reconcile the two.

---

## scope-graphs: drawn by hand from the paper

**No tool emitted this graph.** It is one encoding of the fixture under the ESOP 2015 rules, drawn by hand, so treat it as schema-derived.

Nested boxes are scopes, and nesting is the lexical parent edge `P`.
A `D` node is a declaration and an `R` node is a reference.
An arrow labelled `I` runs from a scope to its import reference, and `associated` runs from a declaration to the scope it names.

```cytoscape
{
  "elements": [
    { "data": { "id": "G", "label": "global scope", "category": "Networking" } },
    { "data": { "id": "S0", "label": "module scope, greet.py", "parent": "G", "category": "Compute" } },
    { "data": { "id": "S2", "label": "class scope, Greeter", "parent": "S0", "category": "Integration" } },
    { "data": { "id": "S1", "label": "module scope, main.py", "parent": "G", "category": "Storage" } },
    { "data": { "id": "S6", "label": "body of main", "parent": "S1", "category": "General" } },

    { "data": { "id": "dmod", "label": "D greet\nmodule, associated scope greet.py", "parent": "G", "variant": "alt" } },
    { "data": { "id": "dfn", "label": "D greet\nline 4", "parent": "S0", "variant": "alt" } },
    { "data": { "id": "dcls", "label": "D Greeter\nline 9, associated scope", "parent": "S0", "variant": "alt" } },
    { "data": { "id": "dinit", "label": "D __init__\nline 12", "parent": "S2", "variant": "alt" } },
    { "data": { "id": "dmeth", "label": "D greet\nline 15", "parent": "S2", "variant": "alt" } },
    { "data": { "id": "dmain", "label": "D main\nline 6", "parent": "S1", "variant": "alt" } },

    { "data": { "id": "rimp", "label": "R greet\nline 3, the import", "parent": "S1" } },
    { "data": { "id": "r8", "label": "R greet\nline 8", "parent": "S6" } },
    { "data": { "id": "r9", "label": "R greet\nline 9", "parent": "S6" } },
    { "data": { "id": "r10c", "label": "R Greeter\nline 10", "parent": "S6" } },
    { "data": { "id": "r10m", "label": "R greet\nline 10, after the dot", "parent": "S6" } },
    { "data": { "id": "r14", "label": "R main\nline 14", "parent": "S1" } },

    { "data": { "source": "rimp", "target": "dmod", "label": "P then D" } },
    { "data": { "source": "S1", "target": "rimp", "label": "I" } },
    { "data": { "source": "dmod", "target": "S0", "label": "associated" } },
    { "data": { "source": "dcls", "target": "S2", "label": "associated" } },
    { "data": { "source": "r8", "target": "dfn", "label": "P, I, D" } },
    { "data": { "source": "r9", "target": "dfn", "label": "P, I, D" } },
    { "data": { "source": "r10c", "target": "dcls", "label": "P, I, D" } },
    { "data": { "source": "r14", "target": "dmain", "label": "D" } },
    { "data": { "source": "r10m", "target": "dmeth", "label": "needs the type of Greeter(...)", "style": "dashed" } }
  ],
  "layout": { "name": "dagre", "rankDir": "LR", "rankSep": 80 },
  "height": 760
}
```

**The paper's calculus stops at the dot.** `R greet` after the dot resolves in the associated scope of whatever `Greeter("Howdy")` returns, and ESOP 2015 has no types to say what that is.
Type-dependent name resolution came in later work, which Statix builds on.
stack-graphs closes the same gap with the scoped `()` symbol shown above, which is a syntax rule rather than a type.

**The import is wider here than in Python.** An ESOP import edge brings in the whole associated scope, not just the names listed.
This fixture does not show the difference, because `greet.py` declares exactly the two names imported.

---

## What the pictures show side by side

| Question | tree-sitter and `treesitter.py` | stack-graphs | LSP | SCIP | scope-graphs |
|---|---|---|---|---|---|
| Sends `.greet` on line 10 to the method? | yes, by receiver heuristic | yes, by the scoped `()` rule | yes, by type | yes, by type, recorded as a symbol string | no, it needs a type |
| Names the calling function? | yes | no, only the position | yes | only through `enclosing_range` on definitions | no |
| Sees `Greeter("Howdy")` as a call? | a call, with no match | a reference to the class | no | a reference to the class | a reference to the class |
| Keeps the import distinct from a use? | the import is not a call | the import is a definition too | not in callHierarchy | no, both are `ReadAccess` | yes, as an `I` edge |
| Counts one call site once? | yes | per position, though the plain calls carry two reference nodes each | no, `fromRanges` repeats | yes, one occurrence | yes |

---

## Rebuilding this page

The graphs are rebuilt from the dumps written by the reproduction block in [README.md](README.md#reproducing-this).
Rendering needs the `richdocs` skill under `.claude/skills/`, which is git-ignored, so a fresh clone must install it first.

```bash
export PATH="$PWD/tmp/cargo/bin:$PWD/tmp/cargo-ts/bin:$PATH"
uv run docs/plans/maintainability/examples/build_graphs.py

uv run --no-project .claude/skills/richdocs/scripts/md2html.py \
    docs/plans/maintainability/examples/hello-python.md --out tmp/richdocs/examples
cp -R docs/plans/maintainability/examples/graphs tmp/richdocs/examples/
uv run --no-project .claude/skills/richdocs/scripts/serve.py tmp/richdocs/examples --open
```
