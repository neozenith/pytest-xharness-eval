#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["lsprotocol>=2024.0.0"]
# ///
"""Extract a call graph from a source tree via any LSP that speaks callHierarchy.

Builds on the repo's own .claude/skills/lsp/scripts/lsp_explorer.py: reuses its
LspSession (JSON-RPC framing, initialize handshake, did_open) and adds the two
callHierarchy requests pyright and typescript-language-server both support, but
that skill does not yet issue.

Why callHierarchy and not semanticTokens: open-source pyright does not implement
textDocument/semanticTokens (that is a Pylance feature), so the skill's index
records 0 references. prepareCallHierarchy + incomingCalls is the supported path
and is semantically a *call* graph rather than a token-coincidence graph.

Usage:
    callgraph.py <source-dir> <out.json> [--lang python|typescript] [--ext .ts,.tsx]

The "layer" of a node is its first path segment under <source-dir>, which is the
declared partition every downstream script scores.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lsp as lx  # noqa: E402  -- the amended fork in this directory

# LSP SymbolKind numbers for things that can be called.
# 6=Method, 9=Constructor, 12=Function. TSX components are Functions or
# Variables holding arrow functions; 13=Variable is included for typescript so
# `const Foo = () => ...` is not invisible.
CALLABLE_KINDS = {6, 9, 12}
CLASS_KINDS = {5, 23}  # Class, Struct

# typescript-language-server reports every inline arrow function as a symbol
# named "map() callback", "filter() callback" and so on. These are not names:
# nobody learns them, nothing calls them by name, and leverage is defined over
# names someone invented. Counting them puts the orphan rate at 73% and says
# nothing. Anonymous lambdas are excluded from the graph by construction.
ANONYMOUS = re.compile(r"\(\) callback$|^<anonymous>$|^\(\)")


def flatten(
    symbols: list[dict[str, Any]],
    out: list[dict[str, Any]],
    kinds: set[int],
    prefix: str = "",
) -> None:
    """documentSymbol returns a tree of raw LSP DocumentSymbols; take every callable.

    Names are qualified with the enclosing class so `_Ledger.assistant` is
    distinguishable from any other `assistant` in the same file.
    """
    for s in symbols:
        name = s.get("name", "")
        qualified = f"{prefix}{name}"
        if s.get("kind") in kinds and not ANONYMOUS.search(name):
            sel = s.get("selectionRange", s.get("range", {}))
            out.append(
                {
                    "name": qualified,
                    "kind": s.get("kind"),
                    "line": sel["start"]["line"] + 1,
                    "col": sel["start"]["character"] + 1,
                }
            )
        child_prefix = f"{qualified}." if s.get("kind") in CLASS_KINDS else prefix
        for child in s.get("children", []) or []:
            flatten([child], out, kinds, child_prefix)


def call_hierarchy_prepare(session: Any, f: Path, line: int, col: int) -> list[dict[str, Any]]:
    """textDocument/prepareCallHierarchy at a 1-indexed position."""
    session.did_open(f)
    req = session._client.send_request(  # noqa: SLF001 - the skill exposes no public passthrough yet
        "textDocument/prepareCallHierarchy",
        {
            "textDocument": {"uri": lx._file_uri(f)},  # noqa: SLF001
            "position": {"line": line - 1, "character": col - 1},
        },
    )
    # wait_response already unwraps the JSON-RPC envelope: it returns `result`.
    result = session._client.wait_response(req)  # noqa: SLF001
    return result if isinstance(result, list) else []


def incoming_calls(session: Any, item: dict[str, Any]) -> list[dict[str, Any]]:
    """callHierarchy/incomingCalls for a prepared item; returns the caller items."""
    req = session._client.send_request("callHierarchy/incomingCalls", {"item": item})  # noqa: SLF001
    result = session._client.wait_response(req)  # noqa: SLF001
    if not isinstance(result, list):
        return []
    # fromRanges lists EVERY call site inside that caller, not just one. A
    # caller that calls the target five times yields one item with five ranges.
    # Collapsing to a set of (caller, callee) pairs therefore measures distinct
    # calling functions, not call sites, so the count is carried through.
    return [(c["from"], len(c.get("fromRanges") or [1])) for c in result if "from" in c]


def node_key_for(item: dict[str, Any], repo: Path) -> str | None:
    """Map a callHierarchy item back onto our node id (path:line, 1-indexed)."""
    uri = item.get("uri", "")
    if not uri.startswith("file://"):
        return None
    path = Path(uri[7:])
    try:
        rel = path.relative_to(repo)
    except ValueError:
        return None
    line = item.get("selectionRange", item.get("range", {})).get("start", {}).get("line")
    if line is None:
        return None
    return f"{rel}:{line + 1}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path, help="directory to walk, relative to the repo root")
    ap.add_argument("out", type=Path, help="where to write the graph JSON")
    ap.add_argument("--lang", default="python", help="language for the LSP server lookup")
    ap.add_argument("--ext", default=".py", help="comma-separated file extensions to index")
    ap.add_argument(
        "--include-variables",
        action="store_true",
        help="also treat Variable symbols as callable (arrow-function components)",
    )
    ap.add_argument(
        "--exclude",
        default="",
        help="comma-separated path fragments to skip, e.g. __tests__,.test.",
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=None,
        help=(
            "workspace root handed to the LSP, if it differs from the repo root. "
            "typescript-language-server resolves its tsserver from here, so a "
            "webapp in a subdirectory must pass its own package root."
        ),
    )
    args = ap.parse_args()

    src = (REPO / args.source).resolve()
    exts = tuple(e.strip() for e in args.ext.split(","))
    kinds = CALLABLE_KINDS | ({13} if args.include_variables else set())

    skip = [s.strip() for s in args.exclude.split(",") if s.strip()]
    files = sorted(
        f
        for f in src.rglob("*")
        if f.suffix in exts and f.is_file() and not any(s in str(f) for s in skip)
    )
    print(f"[1/4] {len(files)} files under {src.relative_to(REPO)}", file=sys.stderr)

    lsp_root = (REPO / args.root).resolve() if args.root else REPO
    manager = lx.LanguageServerManager(args.lang)
    session = manager.start(lsp_root)
    try:
        # Servers default to analysing open files only: a file never opened
        # contributes no incoming calls. Opening every file first is what makes
        # the graph whole.
        for f in files:
            session.did_open(f)
        print(f"[2/4] opened {len(files)} documents", file=sys.stderr)

        nodes: dict[str, dict[str, Any]] = {}
        positions: list[tuple[str, Path, int, int]] = []

        for f in files:
            try:
                syms: list[dict[str, Any]] = []
                flatten(session.document_symbol(f), syms, kinds)
            except Exception as e:  # noqa: BLE001
                print(f"  ! documentSymbol {f.name}: {e}", file=sys.stderr)
                continue
            rel = f.relative_to(REPO)
            layer_rel = f.relative_to(src)
            layer = layer_rel.parts[0] if len(layer_rel.parts) > 1 else "<root>"
            for s in syms:
                key = f"{rel}:{s['line']}"
                nodes[key] = {
                    "id": key,
                    "name": s["name"],
                    "file": str(rel),
                    "layer": layer,
                    "line": s["line"],
                    "kind": s["kind"],
                }
                positions.append((key, f, s["line"], s["col"]))

        print(f"[3/4] {len(nodes)} callable definitions", file=sys.stderr)

        edges: dict[tuple[str, str], int] = {}
        for i, (key, f, line, col) in enumerate(positions):
            if i % 100 == 0:
                print(f"      callHierarchy {i}/{len(positions)}", file=sys.stderr)
            items = call_hierarchy_prepare(session, f, line, col)
            if not items:
                continue
            for caller, sites in incoming_calls(session, items[0]):
                src_key = node_key_for(caller, REPO)
                if src_key and src_key in nodes and src_key != key:
                    edges[(src_key, key)] = edges.get((src_key, key), 0) + sites

        print(f"[4/4] {len(edges)} call edges", file=sys.stderr)

        out = {
            "source": str(src.relative_to(REPO)),
            "nodes": list(nodes.values()),
            "edges": [{"source": a, "target": b, "sites": n} for (a, b), n in sorted(edges.items())],
        }
        dest = REPO / args.out
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"wrote {dest.relative_to(REPO)}", file=sys.stderr)
    finally:
        manager.stop()


if __name__ == "__main__":
    main()
