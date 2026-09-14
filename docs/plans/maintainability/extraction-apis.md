# Extraction APIs: what LSP and tree-sitter can be asked for

**Status:** reference for this directory only. **Before you start:** [tools/README.md](tools/README.md).

Every `GR` metric in [GLOSSARY.md](GLOSSARY.md) runs on a call graph that one of two instruments produced.
This file catalogues what each instrument offers, by exact method and API name.
It is a capability register, not an argument.
The argument about which graph to trust is [What we still cannot extract](README.md#what-we-still-cannot-extract), and the open parts are group 1 of [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

Cite a method string here rather than describing it in prose.
A capability absent from this file is one no extractor in `tools/` can reach today.

[ast-data-models.md](ast-data-models.md) is the layer beneath this one.
It models what each provider stores, as one ERD per provider, where this file lists what each can be asked.

---

<details>
<summary><b>Table of Contents</b></summary>
<!--TOC-->

- [Extraction APIs: what LSP and tree-sitter can be asked for](#extraction-apis-what-lsp-and-tree-sitter-can-be-asked-for)
  - [Which instrument answers which question](#which-instrument-answers-which-question)
  - [LSP: a position, answered by a server](#lsp-a-position-answered-by-a-server)
  - [LSP lifecycle](#lsp-lifecycle)
  - [LSP document synchronisation](#lsp-document-synchronisation)
  - [LSP navigation and relationships](#lsp-navigation-and-relationships)
  - [LSP structure and symbols](#lsp-structure-and-symbols)
  - [LSP semantic and informational](#lsp-semantic-and-informational)
  - [LSP edit and transform](#lsp-edit-and-transform)
  - [LSP workspace, window and telemetry](#lsp-workspace-window-and-telemetry)
  - [The LSP types that carry a graph](#the-lsp-types-that-carry-a-graph)
  - [Tree-sitter: a grammar, applied to a buffer](#tree-sitter-a-grammar-applied-to-a-buffer)
  - [The tree-sitter parser](#the-tree-sitter-parser)
  - [The tree and its nodes](#the-tree-and-its-nodes)
  - [Cursors and incremental parsing](#cursors-and-incremental-parsing)
  - [The tree-sitter query language](#the-tree-sitter-query-language)
  - [The standard query files](#the-standard-query-files)
  - [The layers above tree-sitter](#the-layers-above-tree-sitter)
  - [Batch index formats](#batch-index-formats)
  - [What neither instrument can see](#what-neither-instrument-can-see)
  - [What this changes for the open questions](#what-this-changes-for-the-open-questions)
  - [References](#references)

<!--TOC-->
</details>

---

## Which instrument answers which question

| Property | LSP | tree-sitter |
|---|---|---|
| Unit of work | one position in one open document | one buffer |
| Output | a typed answer | a concrete syntax tree |
| Name resolution | yes, with full type inference | **no**, it matches names only |
| Cross-file | yes | no |
| Cross-language | no, one server per language | no, one grammar per language |
| Whole boundary nesting at once | no, `documentSymbol` is per file | yes |
| Error tolerance | server-dependent | total, through `ERROR` and `MISSING` nodes |
| Incremental | through `textDocument/didChange` | through `ts_tree_edit`, reusing subtrees |
| Cost | server startup and an index, seconds to minutes | microseconds per edit |
| Failure mode | **a plausible empty result** | a visible `ERROR` node |

The last row is the expensive one.
Six of the seven extraction failures on record produce a plausible wrong answer rather than an error.

**Takeaway:** ask an LSP when the question needs types, and tree-sitter when it needs structure.

---

## LSP: a position, answered by a server

The protocol is JSON-RPC 2.0 over stdio or a socket.
Every capability is negotiated once, at `initialize`.
The client sends `ClientCapabilities` and the server answers with `ServerCapabilities`.
**A capability the server does not advertise does not exist**, and asking for it returns an error or an empty result.
A server may also register a capability later, through `client/registerCapability`.

This is why `tools/lsp.py` treats a missing server as fatal.
A server that never started advertises nothing, and every subsequent query answers empty.

**The rule has a measured exception.** The recorded `typescript-language-server` reply advertises no `callHierarchyProvider`, yet answers `prepareCallHierarchy` correctly.
`tools/lsp.py` gates nothing on `ServerCapabilities` except the semantic token legend, so every TypeScript edge here came from an unadvertised method.

---

## LSP lifecycle

| Method | Kind |
|---|---|
| `initialize` | request, exchanges capabilities and `rootUri` or `workspaceFolders` |
| `initialized` | notification, the client is ready |
| `shutdown` then `exit` | request then notification |
| `client/registerCapability`, `client/unregisterCapability` | server to client request |
| `$/cancelRequest` | notification, cancels an in-flight request |
| `$/progress` | notification, carries work-done and partial-result streaming |
| `$/setTrace`, `$/logTrace` | notification, trace verbosity |

---

## LSP document synchronisation

| Method | Capability field |
|---|---|
| `textDocument/didOpen`, `didChange`, `didClose`, `didSave` | `textDocumentSync` |
| `textDocument/willSave`, `willSaveWaitUntil` | `textDocumentSync` |
| `notebookDocument/didOpen`, `didChange`, `didSave`, `didClose` | `notebookDocumentSync` |

`textDocumentSync` is one of `None`, `Full` or `Incremental`.

This layer holds the openFilesOnly trap.
A server asked about a position inside a closed document answers with an empty result rather than an error.
Holding the whole workspace open is what took this repository from 0 edges to 380.

---

## LSP navigation and relationships

This is the graph-bearing subset, and the only part of the protocol a call graph needs.

| Method | Returns | Capability field |
|---|---|---|
| `textDocument/declaration` | `Location`, `Location[]` or `LocationLink[]` | `declarationProvider` |
| `textDocument/definition` | `Location`, `Location[]` or `LocationLink[]` | `definitionProvider` |
| `textDocument/typeDefinition` | `Location`, `Location[]` or `LocationLink[]` | `typeDefinitionProvider` |
| `textDocument/implementation` | `Location`, `Location[]` or `LocationLink[]` | `implementationProvider` |
| `textDocument/references` | `Location[]`, with `context.includeDeclaration` | `referencesProvider` |
| `textDocument/prepareCallHierarchy` | `CallHierarchyItem[]` | `callHierarchyProvider` |
| `callHierarchy/incomingCalls` | `from` plus **`fromRanges`** | `callHierarchyProvider` |
| `callHierarchy/outgoingCalls` | `to` plus `fromRanges` | `callHierarchyProvider` |
| `textDocument/prepareTypeHierarchy` | `TypeHierarchyItem[]` | `typeHierarchyProvider` |
| `typeHierarchy/supertypes`, `typeHierarchy/subtypes` | `TypeHierarchyItem[]` | `typeHierarchyProvider` |
| `textDocument/documentHighlight` | occurrences in one file, kinded `Text`, `Read` or `Write` | `documentHighlightProvider` |
| `textDocument/moniker` | a cross-repository symbol identity | `monikerProvider` |

`fromRanges` is what separates a distinct caller from a call site.
It is the protocol-native source of [GR-SIT-10](GLOSSARY.md#gr-sit-10-call-site-weight), and the 380 against 515 gap recorded in `tools/lsp.py`.
**515 is an upper bound.** pyright repeats a range for one method call, as [examples/](examples/README.md) measured, and `tools/lsp.py` counts `fromRanges` without deduplicating.

`documentHighlight` is kinded, so it distinguishes a mutation from a read inside one file.
Nothing in this work uses that yet.

---

## LSP structure and symbols

| Method | Returns | Capability field |
|---|---|---|
| `textDocument/documentSymbol` | a nested `DocumentSymbol[]`, or a flat `SymbolInformation[]` | `documentSymbolProvider` |
| `workspace/symbol` | project-wide symbol search by query string | `workspaceSymbolProvider` |
| `workspaceSymbol/resolve` | fills in a lazily returned symbol's `location` | `workspaceSymbolProvider` |
| `textDocument/foldingRange` | `FoldingRange[]`, kinded `comment`, `imports` or `region` | `foldingRangeProvider` |
| `textDocument/selectionRange` | nested expand-selection ranges | `selectionRangeProvider` |

A `DocumentSymbol` carries `name`, `detail`, `kind`, `tags`, `range`, `selectionRange` and `children`, plus a `deprecated` flag superseded by `tags`.
`range` spans the whole definition and `selectionRange` spans the name alone.
That pair is what distinguishes a function from the identifier naming it.

---

## LSP semantic and informational

| Method | Capability field |
|---|---|
| `textDocument/hover` | `hoverProvider` |
| `textDocument/signatureHelp` | `signatureHelpProvider` |
| `textDocument/completion`, `completionItem/resolve` | `completionProvider` |
| `textDocument/semanticTokens/full`, `/full/delta`, `/range` | `semanticTokensProvider` |
| `textDocument/inlayHint`, `inlayHint/resolve` | `inlayHintProvider` |
| `textDocument/inlineValue` | `inlineValueProvider` |
| `textDocument/inlineCompletion`, added in 3.18 | `inlineCompletionProvider` |
| `textDocument/documentLink`, `documentLink/resolve` | `documentLinkProvider` |
| `textDocument/documentColor`, `textDocument/colorPresentation` | `colorProvider` |
| `textDocument/publishDiagnostics`, the push form | none |
| `textDocument/diagnostic`, `workspace/diagnostic`, the pull form added in 3.17 | `diagnosticProvider` |

Semantic tokens are optional, and open-source pyright does not implement them.
They are a Pylance feature, and the empty array pyright returns is not an error.
That is the failure that recorded 2780 definitions and zero references while exiting 0.

---

## LSP edit and transform

| Method | Capability field |
|---|---|
| `textDocument/codeAction`, `codeAction/resolve` | `codeActionProvider` |
| `textDocument/rename`, `textDocument/prepareRename` | `renameProvider` |
| `textDocument/formatting`, `rangeFormatting`, `onTypeFormatting` | the matching `document*FormattingProvider` |
| `textDocument/codeLens`, `codeLens/resolve` | `codeLensProvider` |
| `textDocument/linkedEditingRange` | `linkedEditingRangeProvider` |
| `workspace/executeCommand` | `executeCommandProvider` |
| `workspace/applyEdit` | server to client request |

`codeActionProvider` advertises `codeActionKinds` such as `quickfix`, `refactor.extract` and `source.organizeImports`.
A server that advertises `refactor.extract` can perform the extraction transform the rearrangement sweep simulates with stub wrappers.
Neither recorded server advertises it, so the route is untested here.
That is one route to closing M2 in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

---

## LSP workspace, window and telemetry

| Group | Methods |
|---|---|
| Configuration | `workspace/didChangeConfiguration`, `workspace/configuration` |
| Folders | `workspace/workspaceFolders`, `workspace/didChangeWorkspaceFolders` |
| Watched files | `workspace/didChangeWatchedFiles` |
| File operations | `workspace/willCreateFiles`, `workspace/didCreateFiles`, `workspace/willRenameFiles`, `workspace/didRenameFiles`, `workspace/willDeleteFiles`, `workspace/didDeleteFiles` |
| Refresh | `workspace/semanticTokens/refresh`, `workspace/inlayHint/refresh`, `workspace/inlineValue/refresh`, `workspace/codeLens/refresh`, `workspace/diagnostic/refresh` |
| Window | `window/showMessage`, `window/showMessageRequest`, `window/logMessage`, `window/showDocument` |
| Progress | `window/workDoneProgress/create`, `window/workDoneProgress/cancel` |
| Telemetry | `telemetry/event` |

---

## The LSP types that carry a graph

**`SymbolKind`** is an integer enum of 26 members.

```
1  File          8  Field         15 String       22 EnumMember
2  Module        9  Constructor   16 Number       23 Struct
3  Namespace    10  Enum          17 Boolean      24 Event
4  Package      11  Interface     18 Array        25 Operator
5  Class        12  Function      19 Object       26 TypeParameter
6  Method       13  Variable      20 Key
7  Property     14  Constant      21 Null
```

`SymbolTag` has one member, `Deprecated`.

**`CallHierarchyItem`** carries `name`, `kind`, `tags`, `detail`, `uri`, `range`, `selectionRange` and `data`.
An incoming call is that item plus `fromRanges`, which lists every call site inside the caller.

**Semantic token types**, the standard set as of LSP 3.18.

```
namespace type class enum interface struct typeParameter parameter
variable property enumMember event function method macro keyword
modifier comment string number regexp operator decorator label
```

**Semantic token modifiers**, the standard set.
A server declares its own legend, so it may omit standard names and add its own.

```
declaration definition readonly static deprecated
abstract async modification documentation defaultLibrary
```

`defaultLibrary` marks a call into the standard library.
It is the only protocol-native way to exclude stdlib edges from a graph without a heuristic.

Tokens arrive as a flat `uinteger[]` in groups of five.

```
deltaLine  deltaStart  length  tokenType  tokenModifiers
```

`tokenModifiers` is a bitset.
`deltaLine` is relative to the previous token, and `deltaStart` is relative to its start only when both sit on the same line.

---

## Tree-sitter: a grammar, applied to a buffer

A C library plus one compiled grammar per language.
It produces a concrete syntax tree, so every token is present, punctuation included.
There is no project model, no import resolution and no type inference.

The reason to prefer it here is not speed.
The syntax tree carries the whole within-file hierarchy at once.
Conductance can therefore be scored at class and nesting level as well as at the folder.
The folder and language levels still come from file paths.

---

## The tree-sitter parser

| API | Capability |
|---|---|
| `ts_parser_new`, `ts_parser_set_language` | bind one `TSLanguage` |
| `ts_parser_parse_string` | parse a whole buffer |
| `ts_parser_parse` with a `TSInput` | parse from a callback, for ropes and streams |
| `TSInputEncoding` | `UTF8`, `UTF16LE`, `UTF16BE` or `Custom` |
| `TSInput.decode` | the `TSDecodeFunction` used when the encoding is `Custom` |
| `ts_parser_set_included_ranges` | parse only the given `TSRange[]`, which is how injection works |
| `ts_parser_parse_with_options` | bound or cancel the parse through `TSParseOptions.progress_callback` |
| `ts_parser_reset` | discard partial state |

---

## The tree and its nodes

| API | Capability |
|---|---|
| `ts_tree_root_node` | the root |
| `ts_tree_copy` | a shallow copy, cheap enough to give each thread its own, because a `TSTree` is not thread safe |
| `ts_node_type`, `ts_node_symbol` | which grammar rule this node is |
| `ts_node_start_byte`, `ts_node_end_byte` | byte span |
| `ts_node_start_point`, `ts_node_end_point` | a `TSPoint` of zero-based row and column |
| `ts_node_parent`, `ts_node_child`, `ts_node_child_count` | raw traversal, anonymous nodes included |
| `ts_node_next_sibling`, `ts_node_prev_sibling` | raw sibling walk |
| `ts_node_is_named` | a named node is a grammar rule, an anonymous one is a literal token |
| `ts_node_named_child`, `ts_node_named_child_count` | traversal that skips anonymous nodes |
| `ts_node_child_by_field_name`, `ts_node_child_by_field_id` | access a child by its role |
| `ts_language_field_id_for_name`, `ts_language_field_name_for_id` | convert between a field name and its id |
| `ts_node_is_extra` | the node matched an `extras` rule, such as a comment |
| `ts_node_is_missing`, `ts_node_is_error`, `ts_node_has_error` | error recovery state |
| `ts_node_descendant_for_byte_range`, `..._for_point_range` | look a node up by position |
| `ts_node_string` | an S-expression dump |

**A field is the only robust way to read a child.** `name:`, `body:` and `condition:` are stable across grammar releases, and a child index is not.
`tools/treesitter.py` reads `child_by_field_name("name")` for exactly this reason.

**Parsing never fails.** Unrecognised text becomes an `ERROR` node.
A token the grammar required but the source omitted becomes a zero-width `MISSING` node.
Both are queryable, so a broken file is visible rather than silent.

---

## Cursors and incremental parsing

`TSTreeCursor` is the stateful walk, and the efficient way to traverse a large tree.
It keeps its own stack, so it must be freed with `ts_tree_cursor_delete`.

| API | Capability |
|---|---|
| `ts_tree_cursor_new` | start a walk at a node |
| `goto_first_child`, `goto_next_sibling`, `goto_parent` | move |
| `goto_first_child_for_byte` | descend toward a byte offset |
| `current_field_name`, `current_depth` | where the cursor is, and in what role |

Incremental parsing is three calls.

```
ts_tree_edit(tree, &TSInputEdit{...})   shift node positions to match the new text
ts_parser_parse(parser, tree, input)    reuse every unchanged subtree
ts_tree_get_changed_ranges(old, new)    report what actually differs
```

`TSInputEdit` carries `start_byte`, `old_end_byte`, `new_end_byte` and the three matching points.
`ts_node_edit` updates a node handle held across the edit.

---

## The tree-sitter query language

Queries are compiled patterns over the tree.
The runtime is `ts_query_new`, a `TSQueryCursor`, and `ts_query_cursor_exec`.
`ts_query_cursor_set_byte_range` and `set_point_range` scope a query to part of a file.
`ts_query_cursor_set_max_start_depth` bounds how deep a pattern may start.
Matches arrive as a `TSQueryMatch` holding a `TSQueryCapture[]`.

**Pattern syntax.**

| Feature | Form | Meaning |
|---|---|---|
| Pattern | `(function_definition)` | match a named node |
| Nesting | `(call (identifier))` | a child relationship |
| Field | `(call function: (identifier))` | a child in a named field |
| Negated field | `(class_definition !superclasses)` | a node lacking that field |
| Anonymous node | `"return"` | a literal token |
| Named wildcard | `(_)` | any named node |
| Full wildcard | `_` | any node, named or anonymous |
| Capture | `@name` | tag the preceding node |
| Supertype | `(primary_expression/identifier)` | match a subtype of a grammar supertype |
| Recovery nodes | `(ERROR)`, `(MISSING)` | match the parser's own error states |

**Operators.**

| Operator | Meaning |
|---|---|
| `?` | zero or one |
| `*` | zero or more |
| `+` | one or more |
| `(...)` | group a sibling sequence and match it as a unit |
| `[...]` | alternation, any one of the listed patterns |
| `.` | anchor, constrain to the first named child, the last named child or immediate adjacency, ignoring anonymous nodes |

**Predicates and directives.** These are evaluated by the host binding rather than the C core, so a binding may omit one.

| Name | Effect |
|---|---|
| `#eq?`, `#not-eq?` | capture text equals a string or another capture |
| `#any-eq?`, `#any-not-eq?` | the same test over a quantified capture |
| `#match?`, `#not-match?` | a regular expression against capture text |
| `#any-match?`, `#any-not-match?` | the same regex over a quantified capture |
| `#any-of?`, `#not-any-of?` | capture text is one of several strings |
| `#is?`, `#is-not?` | assert a property on a capture |
| `#set!` | attach a key and value to the match |
| `#select-adjacent!` | tagging system only, keep capture nodes adjacent to another capture |
| `#strip!` | tagging system only, remove regex-matching text from a capture |

---

## The standard query files

A grammar may ship these under `queries/`, by convention rather than by the C API, and none is guaranteed.
The pinned `tree-sitter-python` ships `highlights.scm` and `tags.scm`, and `tree-sitter-typescript` adds `locals.scm`.
Neither ships `injections.scm`.

| File | Captures | Purpose |
|---|---|---|
| `highlights.scm` | dotted names such as `function`, `function.builtin`, `type`, `keyword`, `string` | syntax highlighting |
| `locals.scm` | `@local.scope`, `@local.definition`, `@local.reference` | lexical scope resolution |
| `injections.scm` | `@injection.content`, `@injection.language`, and `#set!` keys `injection.language`, `injection.combined`, `injection.include-children`, `injection.self` and `injection.parent` | embedded languages, through included ranges |
| `tags.scm` | the roles below, plus `@name` and `@doc` | code navigation symbols |

The documented `tags.scm` roles are `@definition.class`, `@definition.function`, `@definition.interface`, `@definition.method`, `@definition.module`, `@reference.call`, `@reference.class` and `@reference.implementation`.
The pinned grammars differ from that list, because Python emits `@definition.constant` and TypeScript emits `@reference.type`, and neither emits `@reference.implementation`.

**`locals.scm` is the one name binding tree-sitter offers on its own, where a grammar ships one.** It is lexical, so it resolves a local variable and never an import.
The pinned Python grammar ships none, and the TypeScript one only marks parameters as definitions, with no scopes and no references.
`tools/treesitter.py` resolves by name and does not read it, which is one source of the ambiguity rate that tool reports.

**`tags.scm` is the closest thing to a call graph shipped with a grammar.** It is still name-level, so it identifies a call site without saying which definition it reaches.

---

## The layers above tree-sitter

| Project | What it adds |
|---|---|
| `tree-sitter-graph` | a DSL that walks a syntax tree with queries and builds an arbitrary attributed graph |
| `tree-sitter-stack-graphs` | declarative name-binding rules built on `tree-sitter-graph`, producing a `stack-graphs` graph |

A stack graph has eight node kinds, and three of them carry the idea.
A *push symbol* node is a reference, a *pop symbol* node is a definition, and a *scope* node bounds visibility.
Resolution is a path search carrying a symbol stack and a scope stack.

The property that matters here is what it does not need.
Stack graphs resolve names incrementally, per file, **with no build system**.
GitHub announced precise code navigation built on them for Python repositories that were never configured for it.
The `github/stack-graphs` repository was archived in 2025, with rulesets for Java, JavaScript, Python and TypeScript.

`tree-sitter-graph` is the more general of the two.
It decouples what the tree says from what graph you want, which is the shape [G3](OPEN_QUESTIONS.md#1-is-the-call-graph-right) needs for a declared-edge format.

The stack-graphs entity model, and the partial paths that make it incremental, are in [ast-data-models.md](ast-data-models.md).
`tree-sitter-graph` is not modelled separately there, because every node or edge it builds is a stack-graphs one.

---

## Batch index formats

LSP is interactive by design, and answers one position at a time.
Two formats serialise the same information for a whole repository.

| Format | Shape | Status |
|---|---|---|
| LSIF | the LSP graph as a vertex and edge adjacency list, with opaque string or number ids and `resultSet` indirection | superseded in practice |
| SCIP | Protobuf, organised per document rather than as one adjacency list | the current option |

SCIP's core types are `Document`, `Occurrence`, `SymbolInformation` and `SymbolRole`.
An `Occurrence` binds a source range to a symbol.
`SymbolRole` is a bitmask whose members include `Definition`, `Import`, `WriteAccess`, `ReadAccess`, `Generated` and `Test`.

Symbols are human-readable strings rather than integers.
That bounds the blast radius of an indexer bug, which is the defect class that cost this work the most time.
Indexers exist for more than a dozen languages, including Python, TypeScript, Java, Go and Rust.

**Takeaway:** SCIP is the format designed for the question `graphdata.py` asks, and it is streamable and parallel-indexable.

SCIP is modelled field by field in [ast-data-models.md](ast-data-models.md), and LSIF is listed there as superseded.
[examples/](examples/README.md) records what both SCIP indexers actually emitted for one Python and one React fixture.

---

## What neither instrument can see

| What | Why no method reaches it |
|---|---|
| A dispatch table, such as a `Record<string, fn>` | the edge exists only at runtime, and the source holds a lookup |
| A decorator or plugin registry, such as `pluggy` | the caller is the framework, and it is not in the tree |
| Anything reached by reflection | the name is computed |
| A cross-language contract | one grammar and one server each stop at a language boundary |

`textDocument/moniker` and SCIP's string symbols are the only standardised cross-artifact identities.
Neither models `emit/index.py` writing `report/index.json` and `report-ui/src/lib/types.ts` reading it.
That edge has to be declared, which is [G4](OPEN_QUESTIONS.md#1-is-the-call-graph-right).

**Takeaway:** every graph either instrument produces is a lower bound, and a declared-edge format is the only way past it.

---

## What this changes for the open questions

| Question | What this catalogue offers |
|---|---|
| G2, which extractor to trust per language | a `locals.scm` would cut the name-collision ambiguity `treesitter.py` reports, but it would have to be written. `stack-graphs` resolves without a language server, and its repository is archived |
| G3, dispatch tables and registries | `tree-sitter-graph` constructs an edge from a query match rather than from a call node, which is the mechanism a declared-edge format needs |
| G4, cross-language contracts | nothing here reaches it. `moniker` and SCIP are the nearest standards and neither models a written and re-read file |
| G6, call sites against distinct callers | `fromRanges` is protocol-native, and tree-sitter gives the same count by counting match nodes |
| M2, extraction simulated with stubs | a server advertising `refactor.extract` performs the real transform, though neither server on record does |

---

## References

| Source | Contributes |
|---|---|
| [LSP 3.18 specification](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.18/specification/) | every method string, and the capability field each is gated by |
| [LSP 3.17 specification](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/) | call hierarchy, semantic tokens, and the pull diagnostics model |
| [tree-sitter, basic parsing](https://tree-sitter.github.io/tree-sitter/using-parsers/2-basic-parsing.html) | the node API, and named against anonymous nodes |
| [tree-sitter, advanced parsing](https://tree-sitter.github.io/tree-sitter/using-parsers/3-advanced-parsing.html) | incremental parsing, included ranges, and tree copying |
| [tree-sitter, query syntax](https://tree-sitter.github.io/tree-sitter/using-parsers/queries/1-syntax.html) | patterns, fields, wildcards and supertypes |
| [tree-sitter, query operators](https://tree-sitter.github.io/tree-sitter/using-parsers/queries/2-operators.html) | quantifiers, groups, alternations and anchors |
| [tree-sitter, predicates and directives](https://tree-sitter.github.io/tree-sitter/using-parsers/queries/3-predicates-and-directives.html) | every built-in predicate and directive |
| [tree-sitter, code navigation](https://tree-sitter.github.io/tree-sitter/4-code-navigation.html) | the `tags.scm` roles |
| [tree-sitter, syntax highlighting](https://tree-sitter.github.io/tree-sitter/3-syntax-highlighting.html) | the four standard query files and their captures |
| [Introducing stack graphs](https://github.blog/open-source/introducing-stack-graphs/) | the push, pop and scope node model |
| [github/stack-graphs](https://github.com/github/stack-graphs) | the four language rulesets, in an archived repository |
| [SCIP](https://scip-code.org/) | the indexer list |
| [scip.proto](https://github.com/scip-code/scip/blob/main/scip.proto) | `Occurrence`, `SymbolRole` and the document-centric shape |
| [Announcing SCIP](https://sourcegraph.com/blog/announcing-scip) | why readable symbol strings replaced LSIF's opaque ids |

Method names were read from the specifications on 14 September 2026.
The mapping from a capability to an open question is ours, not a cited result.
