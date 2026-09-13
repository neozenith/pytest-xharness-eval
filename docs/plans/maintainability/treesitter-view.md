# What tree-sitter sees

**Status:** exploration, no findings claimed. **Before you start:** nothing.
This is a look at the raw material, not an argument.

Everything measured so far has been derived from tree-sitter and then thrown away except for two numbers.
This page shows what was actually available.

---

<details>
<summary><b>Table of Contents</b></summary>
<!--TOC-->

- [What tree-sitter sees](#what-tree-sitter-sees)
  - [The two codebases, side by side](#the-two-codebases-side-by-side)
  - [The Python library](#the-python-library)
  - [The TypeScript webapp](#the-typescript-webapp)
  - [Which of the grammar each codebase speaks](#which-of-the-grammar-each-codebase-speaks)
  - [Two things we had and never used](#two-things-we-had-and-never-used)

<!--TOC-->
</details>

---

## The two codebases, side by side

| | Python library | TypeScript webapp |
|---|---|---|
| files | 45 | 73 |
| definitions | 312 | 323 |
| call sites | 1,572 | **2,285** |
| file-to-file edges | 88 | **196** |
| AST nodes | 34,701 | 48,563 |
| node kinds used | 89 | 120 |
| node kinds the grammar defines | 128 | 202 |
| **vocabulary coverage** | **69.5%** | **59.4%** |
| **maximum nesting depth** | **21** | **66** |
| mean nesting depth | 7.23 | 9.95 |

A grammar defines a fixed vocabulary of node kinds: 128 named kinds for Python, 202 for TypeScript with JSX.
Neither codebase uses all of them, and the Python one speaks more of its language than the webapp speaks of its.

---

## The Python library

Files grouped by folder, sized by how much is in them, with an edge wherever one file calls a name defined in another.
Hollow files define nothing callable.

```cytoscape
{ "data": "data/tsv-py-files.json" }
```

45 files and 88 file-to-file edges, of which the 37 carrying two or more calls are drawn.
At weight one the picture is hairlines and no architecture.
The layering is visible without being told: `model/` at one end, the entry points at the other.

---

## The TypeScript webapp

```cytoscape
{ "data": "data/tsv-ts-files.json" }
```

73 files and 196 file-to-file edges, of which the 81 carrying two or more calls are drawn.
Denser, flatter, and with a large `components/` cluster that dominates it.

---

## Which of the grammar each codebase speaks

The most common node kinds, as a share of all named AST nodes.

```plotly
{ "data": "data/tsv-kinds.json" }
```

The distributions are not the same shape, which is the point.
A library is mostly calls and attribute access.
A webapp is mostly JSX elements and their attributes.
That is why its grammar has 74 more node kinds while it uses a smaller fraction of them.

---

## Two things we had and never used
A webapp is mostly JSX elements and their attributes.
That is why its grammar has 74 more node kinds while it uses a smaller fraction of them.
**Nesting depth.** Tree-sitter hands over the depth of every node in the same walk that produces everything else, and none of the metrics touched it.

Python tops out at **21** levels, the webapp at **66**.
That is JSX: an element inside an element inside a map inside a component.
Mean depth is 7.23 against 9.95.

Depth needs **no partition at all**, which makes it unlike conductance and modularity.
It is also not gamed by subdivision the way a per-unit count is.
Extracting a function moves nesting from one place to another rather than reducing it, which is the conserved behaviour the two-springs test asks for.
It has not been tested against any of the rearrangements.

**Fields.** Every child in the tree is labelled with the role it plays, `body`, `condition`, `consequence`, `alternative`, `arguments`.
Depth needs **no partition at all**, which makes it unlike conductance and modularity.
It is also not gamed by subdivision the way a per-unit count is.

Nothing here used them beyond `name` and `function`.
They distinguish a call in a condition from a call in a loop body.
That distinction is the difference between cyclomatic and cognitive complexity.

**Takeaway:** the two unused affordances are depth, which needs no partition, and fields, which carry every node's role.
Both are free in the parse already being done.
