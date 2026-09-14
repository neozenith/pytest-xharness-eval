# hello-react, as five providers see it

Every graph on this page is drawn from what a provider actually emitted for [hello-react/](hello-react/).
The numbers behind them are in [README.md](README.md), and [hello-python.md](hello-python.md) is the same page for the Python fixture.

The graphs are data-driven blocks for the `richdocs` viewer, so on GitHub each one shows only a pointer to its JSON.
Render the page with the commands in [Rebuilding this page](#rebuilding-this-page) to see them.

---

<details>
<summary><b>Table of Contents</b></summary>
<!--TOC-->

- [hello-react, as five providers see it](#hello-react-as-five-providers-see-it)
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

Two TSX files and twenty-two lines, with one component of each definition shape.

```tsx
// src/Greeting.tsx
export function Greeting({ name }: { name: string }) {
  return <h1>Hello, {name}!</h1>;
}

export const Shout = ({ name }: { name: string }) => (
  <strong>{name.toUpperCase()}</strong>
);
```

```tsx
// src/App.tsx
import { Greeting, Shout } from "./Greeting";

export default function App() {
  return (
    <div>
      <Greeting name="world" />
      <Greeting name="again" />
      <Shout name="world" />
    </div>
  );
}
```

Doc comments are omitted above, so line numbers on this page refer to the files on disk.
The questions are whether `<Greeting />` is a use of `Greeting` at all, and whether the `const` arrow component survives.

---

## How much each provider hands back

Twenty-two lines of TSX produce anything from two call edges to 699 graph nodes.

```plotly
{ "data": "graphs/hello-react-sizes.json" }
```

**The stack graph is larger than the Python one for fewer lines.** Part of the difference is module plumbing, since the TypeScript rules push the absolute path of every module as symbols.

---

## tree-sitter: a tree, and a call graph built on it by hand

### The syntax tree of App.tsx

tree-sitter emits a tree of typed byte ranges and nothing else.
The graph shows only named nodes, and the shaded ones are leaves, labelled with their source text.

```cytoscape
{ "data": "graphs/hello-react-ts-cst.json" }
```

A self-closing JSX element is a `jsx_self_closing_element` whose name is an `identifier`, the same leaf type as any variable.

### What tools/treesitter.py builds from it

The extractor counts `jsx_opening_element` and `jsx_self_closing_element` as call sites, and matches them to definitions by name.

```cytoscape
{ "data": "graphs/hello-react-ts-callgraph.json" }
```

**JSX is a call here only because the extractor says so.** The grammar has no notion of a call to a component.

**The arrow component survives.** `treesitter.py` names an arrow function after the `const` it is bound to, so `Shout` is a callable.

**Intrinsic elements have nowhere to go.** `div`, `h1` and `strong` are matched like components and find nothing, and neither does `toUpperCase`.

---

## stack-graphs: every reference joined to its definitions

### Node variants

Six of the eight variants appear, with no `drop_scopes` and no `pop_scoped_symbol`.

```plotly
{ "data": "graphs/hello-react-sg-variants.json" }
```

The missing two are a property of the TypeScript rule file, since the Python rules emit both for thirty-one lines.

### Which definition each reference reaches

Each arrow is an answer from the stack-graphs CLI itself, asked about every reference to a component name.
Push nodes are references, and the shaded pop nodes are definitions.

```cytoscape
{ "data": "graphs/hello-react-sg-references.json" }
```

**JSX element names are references.** `<Greeting />` on lines 8 and 9 and `<Shout />` on line 10 each resolve.

**Every JSX use reaches two definitions.** One is the import binding on line 3 of `App.tsx`, and the other is the declaration in `Greeting.tsx`.
Both arrive with equal standing, so a caller that wants the declaration has to walk past the import itself.

**`Shout` carries no `syntax_type`, and resolves anyway.** `Greeting` is tagged `function`, while the `const` component has no tag on either definition.

**The module string is a reference too.** `"./Greeting"` at `3:33` resolves to the top of `Greeting.tsx`.

### One resolution, step by step

This is the path from `<Greeting />` at `App.tsx:8:8` to `Greeting.tsx:3:17`, replayed over the emitted graph with the symbol-stack and scope-stack rules.
The generator refuses to draw it unless the replay reaches the same definitions the CLI reports.
Runs of the same node type are folded, so 64 graph nodes become 34 steps.
Each step shows the symbol stack after it, with the top on the right.

```cytoscape
{ "data": "graphs/hello-react-sg-path.json" }
```

**The module path is spelled out on the symbol stack.** Leaving `App.tsx`, the path pushes one symbol per directory, from `src` up through `pytest-xharness-eval` and `jpeak` to `Users`.
In `Greeting.tsx` twelve pops in a row consume those path symbols and the module name `Greeting`, which was pushed earlier.

That is why a TypeScript stack-graphs database built in one checkout cannot answer queries in another.

---

## LSP: symbols per file, and calls between them

Each box inside a file is a `documentSymbol` result, labelled with its `SymbolKind`.
A box that appears only as a caller, such as a module, comes from `incomingCalls` instead.
Shaded boxes were also answered by `prepareCallHierarchy`, and each arrow is one `callHierarchy/incomingCalls` item with its `fromRanges`.

```cytoscape
{ "data": "graphs/hello-react-lsp.json" }
```

**`Shout` has two kinds.** `documentSymbol` calls it a Constant, kind 14, and `prepareCallHierarchy` calls it a Function, kind 12.
An extractor that filters on the first never asks the second, which is the `CALLABLE_KINDS` defect in [README.md](README.md#lsp).

**JSX usage is an incoming call.** `App` calls `Greeting` from two ranges and `Shout` from one, each at the element name.

This dump was taken with kind 14 added to the callable set, which is the only reason `Shout` appears with an arrow.

---

## SCIP: occurrences pointing at symbol strings

Every occurrence in each document points at the symbol string it names.
Each occurrence is labelled with its document, position and roles, and solid arrows mark definitions.

```cytoscape
{ "data": "graphs/hello-react-scip.json" }
```

**The two definition shapes stay distinguishable.** `Greeting().` carries the method suffix, and `Shout.` carries the plain term suffix.

**References carry no role at all.** scip-typescript writes `symbol_roles` as `0` on every reference, where scip-python writes `ReadAccess`.

**Intrinsic elements resolve across packages.** `div`, `h1` and `strong` point into `@types/react`, and `toUpperCase` into `lib.es5.d.ts`, none of which was indexed.

**Local symbols are private to a document.** SCIP defines a `local N` string as meaningful only inside its own document.
No number repeats across the two documents here, but the generator keys each local by its document so a repeat could never merge.

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
    { "data": { "id": "S0", "label": "module scope, Greeting.tsx", "parent": "G", "category": "Compute" } },
    { "data": { "id": "S1", "label": "module scope, App.tsx", "parent": "G", "category": "Storage" } },
    { "data": { "id": "S2", "label": "body of App", "parent": "S1", "category": "General" } },

    { "data": { "id": "dmod", "label": "D ./Greeting\nmodule, associated scope Greeting.tsx", "parent": "G", "variant": "alt" } },
    { "data": { "id": "dg", "label": "D Greeting\nline 3", "parent": "S0", "variant": "alt" } },
    { "data": { "id": "ds", "label": "D Shout\nline 7", "parent": "S0", "variant": "alt" } },
    { "data": { "id": "dapp", "label": "D App\nline 5", "parent": "S1", "variant": "alt" } },

    { "data": { "id": "rimp", "label": "R ./Greeting\nline 3, the import", "parent": "S1" } },
    { "data": { "id": "r8", "label": "R Greeting\nline 8", "parent": "S2" } },
    { "data": { "id": "r9", "label": "R Greeting\nline 9", "parent": "S2" } },
    { "data": { "id": "r10", "label": "R Shout\nline 10", "parent": "S2" } },
    { "data": { "id": "rdiv", "label": "R div\nline 7", "parent": "S2" } },

    { "data": { "source": "rimp", "target": "dmod", "label": "P then D" } },
    { "data": { "source": "S1", "target": "rimp", "label": "I" } },
    { "data": { "source": "dmod", "target": "S0", "label": "associated" } },
    { "data": { "source": "r8", "target": "dg", "label": "P, I, D" } },
    { "data": { "source": "r9", "target": "dg", "label": "P, I, D" } },
    { "data": { "source": "r10", "target": "ds", "label": "P, I, D" } },
    { "data": { "source": "rdiv", "target": "G", "label": "no declaration in the fixture", "style": "dashed" } }
  ],
  "layout": { "name": "dagre", "rankDir": "LR", "rankSep": 80 },
  "height": 700
}
```

**Every component use resolves without a type.** Unlike the Python method call, nothing here needs the result of an expression, so the paper's calculus is enough.

**The `const` shape is invisible to the model, which is the point.** A declaration is a name at a position, so `Shout` and `Greeting` are the same kind of thing.

**`div` has no declaration to reach.** Its meaning lives in `@types/react`, and this drawing models only the fixture.

---

## What the pictures show side by side

| Question | tree-sitter and `treesitter.py` | stack-graphs | LSP | SCIP | scope-graphs |
|---|---|---|---|---|---|
| Treats `<Greeting />` as a use of `Greeting`? | yes, by an extractor rule | yes, a reference | yes, an incoming call | yes, an occurrence | yes, a reference |
| Keeps the `const` component `Shout`? | yes | yes, with no `syntax_type` | only if the client keeps kind 14 | yes, as `Shout.` | yes |
| Names the calling component? | yes | no, only the position | yes | only through `enclosing_range` on definitions | no |
| Resolves `div`? | no | no | not asked | yes, into `@types/react` | no |
| Portable across checkouts? | yes | no, the path is on the stack | not stored | yes | not stored |

---

## Rebuilding this page

The graphs are rebuilt from the dumps written by the reproduction block in [README.md](README.md#reproducing-this).
Rendering needs the `richdocs` skill under `.claude/skills/`, which is git-ignored, so a fresh clone must install it first.

```bash
export PATH="$PWD/tmp/cargo/bin:$PWD/tmp/cargo-ts/bin:$PATH"
uv run docs/plans/maintainability/examples/build_graphs.py

uv run --no-project .claude/skills/richdocs/scripts/md2html.py \
    docs/plans/maintainability/examples/hello-react.md --out tmp/richdocs/examples
cp -R docs/plans/maintainability/examples/graphs tmp/richdocs/examples/
uv run --no-project .claude/skills/richdocs/scripts/serve.py tmp/richdocs/examples --open
```
