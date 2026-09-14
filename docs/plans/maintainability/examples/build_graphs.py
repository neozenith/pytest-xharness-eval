#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "tree-sitter>=0.25",
#   "tree-sitter-python>=0.25",
#   "tree-sitter-typescript>=0.23",
# ]
# ///
"""Turn what each provider emitted for a fixture into the graphs its richdocs page draws.

Every graph is built from a provider's own output, never from a hand-written
expectation, so a page cannot show an edge no tool produced. The inputs are the
raw dumps the reproduction block in README.md writes under tmp/hello/, plus the
stack-graphs CLI, which is asked for every reference's definitions directly.

The one derived view is the stack-graphs resolution path. It replays the
symbol-stack and scope-stack rules over the emitted graph, and is refused unless
the definitions it reaches are exactly the ones the CLI reports.

Usage, from the repository root, with both stack-graphs binaries on PATH:

    uv run docs/plans/maintainability/examples/build_graphs.py
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from collections import Counter, deque
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DUMPS = REPO / "tmp" / "hello"
OUT = HERE / "graphs"

sys.path.insert(0, str(HERE.parent / "tools"))
import treesitter as T  # noqa: E402  -- the extractor itself, so its rules are the ones drawn
from tree_sitter import Node, Parser  # noqa: E402

# Compound colours are keyed by the brandpack's category names, which carry no
# meaning of their own here. The mapping is fixed so a colour means the same
# role on every page.
ROLE = {
    "file_a": "Compute",
    "file_b": "Storage",
    "external": "General",
    "symbols": "Integration",
    "unresolved": "Security",
    "root": "Networking",
}

FIXTURES: dict[str, dict[str, Any]] = {
    "hello-python": {
        "lang": "python",
        "binary": "tree-sitter-stack-graphs-python",
        "files": ["greet.py", "main.py"],
        "cst_file": "main.py",
        "lsp": "lsp-raw-python.json",
        "scip": "scip-python.json",
        "ts": "ts-python.json",
        "sg": "sg/python",
        "path_at": [("main.py", 10, 28)],
    },
    "hello-react": {
        "lang": "tsx",
        "binary": "tree-sitter-stack-graphs-typescript",
        "files": ["src/Greeting.tsx", "src/App.tsx"],
        "cst_file": "src/App.tsx",
        "lsp": "lsp-raw-react-k14.json",
        "scip": "scip-react.json",
        "ts": "ts-react.json",
        "sg": "sg/react",
        "path_at": [("src/App.tsx", 8, 8)],
    },
}

KIND = {
    2: "Module",
    5: "Class",
    6: "Method",
    7: "Property",
    9: "Constructor",
    12: "Function",
    13: "Variable",
    14: "Constant",
}


def need(path: Path) -> Path:
    if not path.exists():
        sys.exit(f"missing {path.relative_to(REPO)}: run the reproduction block in {HERE.name}/README.md first")
    return path


def write(name: str, payload: dict[str, Any]) -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"  wrote graphs/{name}")


def file_role(files: list[str], name: str) -> str:
    return ROLE["file_a"] if Path(name).name == Path(files[0]).name else ROLE["file_b"]


# --------------------------------------------------------------------------- tree-sitter


def cst(fixture: str, spec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    """The named nodes of one file's concrete syntax tree, and node counts for every file."""
    grammar = T.GRAMMARS[spec["lang"]]
    parser = Parser(grammar["language"]())
    counts = {"all": 0, "named": 0}
    for rel in spec["files"]:
        stack = [parser.parse((HERE / fixture / rel).read_bytes()).root_node]
        while stack:
            n = stack.pop()
            counts["all"] += 1
            counts["named"] += n.is_named
            stack.extend(n.children)

    src = (HERE / fixture / spec["cst_file"]).read_bytes()
    elements: list[dict[str, Any]] = []

    def visit(n: Node, parent: str | None) -> None:
        nid = f"n{len(elements)}"
        text = src[n.start_byte : n.end_byte].decode("utf-8", "replace")
        leaf = n.named_child_count == 0
        label = f"{n.type}\n{text[:24]}" if leaf else n.type
        data: dict[str, Any] = {"id": nid, "label": label}
        if leaf:
            data["variant"] = "alt"
        elements.append({"data": data})
        if parent:
            elements.append({"data": {"source": parent, "target": nid}})
        for c in n.named_children:
            visit(c, nid)

    visit(parser.parse(src).root_node, None)
    nodes = sum(1 for e in elements if "source" not in e["data"])
    graph = {
        "elements": elements,
        "layout": {"name": "dagre", "rankDir": "LR", "rankSep": 36, "nodeSep": 6},
        "height": max(520, nodes * 12),
    }
    return graph, counts


def extractor(fixture: str, spec: dict[str, Any]) -> dict[str, Any]:
    """tools/treesitter.py's call graph, with the calls it could not place drawn beside it."""
    dump = json.loads(need(DUMPS / spec["ts"]).read_text())
    elements: list[dict[str, Any]] = []
    for rel in spec["files"]:
        elements.append(
            {"data": {"id": f"f:{Path(rel).name}", "label": Path(rel).name, "category": file_role(spec["files"], rel)}}
        )
    elements.append({"data": {"id": "unresolved", "label": "calls with no match", "category": ROLE["unresolved"]}})
    for n in dump["nodes"]:
        name = f"{n['cls']}.{n['name']}" if n["cls"] else n["name"]
        elements.append(
            {"data": {"id": n["id"], "label": f"{name}()\nline {n['line']}", "parent": f"f:{Path(n['file']).name}"}}
        )
    for e in dump["edges"]:
        elements.append(
            {
                "data": {
                    "source": e["source"],
                    "target": e["target"],
                    "label": f"{e['sites']} site{'s' * (e['sites'] != 1)}",
                }
            }
        )

    # Replay the extractor's own resolution loop to name what it dropped.
    grammar = T.GRAMMARS[spec["lang"]]
    parser = Parser(grammar["language"]())
    known = {(n["name"], n["cls"] is not None) for n in dump["nodes"]}
    for rel in spec["files"]:
        path = HERE / fixture / rel
        src = path.read_bytes()
        defs: list[dict[str, Any]] = []
        calls: list[dict[str, Any]] = []
        T.walk(parser.parse(src).root_node, src, grammar, defs, calls)
        relrepo = str(path.relative_to(REPO))
        for c in calls:
            caller = T.enclosing(defs, c["at"])
            uid = f"u:{Path(rel).name}:{c['line']}:{c['name']}"
            if caller is None:
                elements.append(
                    {
                        "data": {
                            "id": uid,
                            "label": f"{c['name']}()\nline {c['line']}, no caller",
                            "parent": "unresolved",
                        }
                    }
                )
                continue
            if (c["name"], c["attr"]) in known:
                continue
            if not any(e["data"].get("id") == uid for e in elements):
                elements.append(
                    {"data": {"id": uid, "label": f"{c['name']}\nline {c['line']}", "parent": "unresolved"}}
                )
            elements.append(
                {
                    "data": {
                        "source": f"{relrepo}:{caller['line']}",
                        "target": uid,
                        "label": "no match",
                        "style": "dashed",
                    }
                }
            )
    return {"elements": elements, "layout": {"name": "dagre", "rankDir": "LR"}, "height": 460}


# --------------------------------------------------------------------------- stack-graphs


def sg_graph(spec: dict[str, Any]) -> dict[str, Any]:
    text = need(DUMPS / f"{spec['sg']}.html").read_text()
    return json.loads(re.search(r"let graph = (\{.*?\});\s*$", text, flags=re.S | re.M).group(1))


def span(n: dict[str, Any]) -> tuple[int, int]:
    s = n["source_info"]["span"]["start"]
    return s["line"] + 1, s["column"]["utf8_offset"] + 1


def nkey(i: dict[str, Any]) -> tuple[str | None, int]:
    return (i.get("file"), i["local_id"])


def sg_query(fixture: str, spec: dict[str, Any], positions: list[str]) -> dict[str, list[str]]:
    """Ask the provider's own CLI for every reference's definitions."""
    binary = shutil.which(spec["binary"])
    if binary is None:
        sys.exit(f'{spec["binary"]} is not on PATH: export PATH="$PWD/tmp/cargo/bin:$PWD/tmp/cargo-ts/bin:$PATH"')
    out = subprocess.run(
        [binary, "query", "-D", str(DUMPS / f"{spec['sg']}.sqlite"), "definition", *positions],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    loc = re.compile(r"^\s*(/\S+):(\d+):(\d+):\s*$")
    result: dict[str, list[str]] = {}
    current, collecting = None, False
    for line in out.splitlines():
        head = re.match(r"^(/\S+):(\d+):(\d+): found", line)
        if head:
            current = f"{Path(head.group(1)).name}:{head.group(2)}:{head.group(3)}"
            result.setdefault(current, [])
            collecting = False
            continue
        if "queried reference" in line:
            collecting = False
        elif re.search(r"has (\d+ )?definitions?$", line.strip()):
            collecting = True
        elif collecting and (m := loc.match(line)) and current:
            result[current].append(f"{Path(m.group(1)).name}:{m.group(2)}:{m.group(3)}")
    return result


def sg_census(g: dict[str, Any]) -> dict[str, int]:
    return dict(Counter(n["type"] for n in g["nodes"]))


def sg_references(fixture: str, spec: dict[str, Any], g: dict[str, Any], callables: set[str]) -> dict[str, Any]:
    """Every reference to a callable name, joined to the definitions the CLI returned for it."""
    defs = {}
    for n in g["nodes"]:
        if n.get("is_definition"):
            line, col = span(n)
            defs[f"{Path(n['id']['file']).name}:{line}:{col}"] = n
    refs = {}
    for n in g["nodes"]:
        if n.get("is_reference") and n.get("symbol") in callables:
            line, col = span(n)
            rel = Path(n["id"]["file"]).relative_to(HERE / fixture)
            refs[f"{HERE / fixture / rel}:{line}:{col}"] = n
    answers = sg_query(fixture, spec, sorted(refs))

    elements: list[dict[str, Any]] = []
    for rel in spec["files"]:
        elements.append(
            {"data": {"id": f"f:{Path(rel).name}", "label": Path(rel).name, "category": file_role(spec["files"], rel)}}
        )
    placed = set()
    for pos, found in sorted(answers.items()):
        if not found:
            continue
        file = pos.split(":")[0]
        symbol = next(n["symbol"] for k, n in refs.items() if k.endswith(pos))
        rid = f"r:{pos}"
        elements.append({"data": {"id": rid, "label": f"push {symbol}\n{pos.split(':', 1)[1]}", "parent": f"f:{file}"}})
        for d in found:
            did = f"d:{d}"
            if did not in placed:
                node = defs.get(d, {})
                kind = (node.get("source_info") or {}).get("syntax_type") or "no syntax_type"
                elements.append(
                    {
                        "data": {
                            "id": did,
                            "label": f"pop {node.get('symbol', '?')}\n{d.split(':', 1)[1]}, {kind}",
                            "parent": f"f:{d.split(':')[0]}",
                            "variant": "alt",
                        }
                    }
                )
                placed.add(did)
            elements.append({"data": {"source": rid, "target": did}})
    return {"elements": elements, "layout": {"name": "dagre", "rankDir": "LR", "rankSep": 90}, "height": 760}, answers


def sg_step(n: dict[str, Any], syms: tuple, scopes: tuple) -> tuple[tuple, tuple] | None:
    """One node's effect on the symbol stack and the scope stack, or None if the path is invalid here."""
    t = n["type"]
    if t == "push_symbol":
        return syms + ((n["symbol"], None),), scopes
    if t == "push_scoped_symbol":
        return syms + ((n["symbol"], (nkey(n["scope"]),) + scopes),), scopes
    if t == "pop_symbol":
        return (syms[:-1], scopes) if syms and syms[-1] == (n["symbol"], None) else None
    if t == "pop_scoped_symbol":
        ok = syms and syms[-1][0] == n["symbol"] and syms[-1][1] is not None
        return (syms[:-1], syms[-1][1]) if ok else None
    if t == "drop_scopes":
        return syms, ()
    return syms, scopes


def sg_replay(g: dict[str, Any], start: tuple[str | None, int]) -> list[tuple[tuple[str | None, int], ...]]:
    """Every complete path from one reference, under the symbol-stack and scope-stack rules."""
    nodes = {nkey(n["id"]): n for n in g["nodes"]}
    out: dict[tuple[str | None, int], list] = {}
    for e in g["edges"]:
        out.setdefault(nkey(e["source"]), []).append(nkey(e["sink"]))

    def step(k, syms, scopes):
        return sg_step(nodes[k], syms, scopes)

    first = step(start, (), ())
    queue = deque([(start, first[0], first[1], (start,))])
    seen, found = set(), []
    while queue:
        k, syms, scopes, path = queue.popleft()
        if len(path) > 400 or len(syms) > 48:
            continue
        if len(path) > 1 and nodes[k].get("is_definition") and not syms:
            found.append(path)
        if nodes[k]["type"] == "jump_to_scope":
            if not scopes:
                continue
            nexts, scopes = [scopes[0]], scopes[1:]
        else:
            nexts = out.get(k, [])
        for m in nexts:
            r = step(m, syms, scopes)
            if r is not None and (m, r[0], r[1]) not in seen:
                seen.add((m, r[0], r[1]))
                queue.append((m, r[0], r[1], path + (m,)))
    return found


def sg_path(fixture: str, spec: dict[str, Any], g: dict[str, Any], answers: dict[str, list[str]]) -> dict[str, Any]:
    """The longest resolution path from the headline reference, with runs of one node type folded."""
    rel, line, col = spec["path_at"][0]
    pos = f"{Path(rel).name}:{line}:{col}"
    nodes = {nkey(n["id"]): n for n in g["nodes"]}
    starts = [
        n
        for n in g["nodes"]
        if n.get("is_reference") and str(n["id"].get("file", "")).endswith(rel) and span(n) == (line, col)
    ]
    paths = [p for s in starts for p in sg_replay(g, nkey(s["id"]))]
    if not paths:
        sys.exit(f"replay found no path from {pos}: refusing to draw it")
    reached = sorted({"{}:{}:{}".format(Path(nodes[p[-1]]["id"]["file"]).name, *span(nodes[p[-1]])) for p in paths})
    if reached != sorted(answers.get(pos, [])):
        sys.exit(f"replay reached {reached} but the CLI reports {answers.get(pos)} for {pos}: refusing to draw it")
    path = max(paths, key=len)

    runs: list[list[tuple[str | None, int]]] = []
    for k in path:
        t = nodes[k]["type"]
        if (
            runs
            and nodes[runs[-1][0]]["type"] == t
            and t in ("scope", "push_symbol", "pop_symbol")
            and k != path[-1]
            and runs[-1][0] != path[0]
        ):
            runs[-1].append(k)
        else:
            runs.append([k])

    verb = {
        "push_symbol": "push",
        "pop_symbol": "pop",
        "push_scoped_symbol": "push scoped",
        "pop_scoped_symbol": "pop scoped",
        "scope": "scope",
        "root": "root",
        "jump_to_scope": "jump to scope",
        "drop_scopes": "drop scopes",
    }
    elements: list[dict[str, Any]] = []
    parents = set()
    syms: tuple = ()
    scopes: tuple = ()
    for i, run in enumerate(runs):
        for k in run:
            if nodes[k]["type"] == "jump_to_scope":
                scopes = scopes[1:]
            else:
                syms, scopes = sg_step(nodes[k], syms, scopes)
        first = nodes[run[0]]
        t = first["type"]
        file = first["id"].get("file")
        parent = f"f:{Path(file).name}" if file else "root"
        if parent not in parents:
            label = Path(file).name if file else "shared root"
            role = file_role(spec["files"], file) if file else ROLE["root"]
            elements.append({"data": {"id": parent, "label": label, "category": role}})
            parents.add(parent)
        symbols = " ".join(nodes[k]["symbol"] for k in run if "symbol" in nodes[k])
        count = f" x{len(run)}" if len(run) > 1 else ""
        label = f"{verb[t]}{count}" + (f"\n{symbols[:60]}" if symbols else "")
        if t != "scope":
            shown = " ".join(s for s, _ in syms[-6:])
            label += "\nstack: " + (("... " if len(syms) > 6 else "") + shown if syms else "empty")
        if i == 0:
            label += f"\nreference at {pos}"
        if i == len(runs) - 1:
            label += "\ndefinition at {}:{}:{}".format(Path(file).name, *span(first))
        data: dict[str, Any] = {"id": f"p{i}", "label": label, "parent": parent}
        if t in ("push_symbol", "pop_symbol", "push_scoped_symbol", "pop_scoped_symbol") or i in (0, len(runs) - 1):
            data["variant"] = "alt"
        elements.append({"data": data})
        if i:
            elements.append({"data": {"source": f"p{i - 1}", "target": f"p{i}"}})
    return {
        "elements": elements,
        "layout": {"name": "dagre", "rankDir": "TB", "rankSep": 22, "nodeSep": 20},
        "height": max(600, len(runs) * 58),
        "_path_nodes": len(path),
        "_runs": len(runs),
    }


# --------------------------------------------------------------------------- LSP


def lsp(spec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    """documentSymbol per file, with every incoming call and its fromRanges drawn between them."""
    dump = json.loads(need(DUMPS / spec["lsp"]).read_text())
    elements: list[dict[str, Any]] = []
    counts = {"symbols": 0, "items": 0, "incoming": 0, "fromRanges": 0}
    # Keyed on name as well as line, because a parameter shares its function's line.
    ids: dict[tuple[str, int, str], str] = {}
    for rel in spec["files"]:
        entry = dump["files"][rel]
        parent = f"f:{Path(rel).name}"
        elements.append({"data": {"id": parent, "label": Path(rel).name, "category": file_role(spec["files"], rel)}})
        for s in entry["document_symbols"]:
            raw = s["raw"]
            counts["symbols"] += 1
            line = raw["selectionRange"]["start"]["line"]
            sid = f"s:{Path(rel).name}:{s['qualified']}:{line}:{raw['kind']}"
            ids[(Path(rel).name, line, raw["name"])] = sid
            kind = KIND.get(raw["kind"], str(raw["kind"]))
            elements.append(
                {
                    "data": {
                        "id": sid,
                        "label": f"{s['qualified']}\n{kind} {raw['kind']}, line {line + 1}",
                        "parent": parent,
                    }
                }
            )
    for rel in spec["files"]:
        for ch in dump["files"][rel]["call_hierarchy"]:
            counts["items"] += 1
            prepared = ch["prepared"]
            target = ids.get(
                (Path(prepared["uri"]).name, prepared["selectionRange"]["start"]["line"], prepared["name"])
            )
            if target is None:
                continue
            node = next(e for e in elements if e["data"].get("id") == target)
            node["data"]["label"] += f"\nprepared as {KIND.get(prepared['kind'], prepared['kind'])} {prepared['kind']}"
            node["data"]["variant"] = "alt"
            for call in ch["incoming"]:
                counts["incoming"] += 1
                counts["fromRanges"] += len(call["fromRanges"])
                frm = call["from"]
                source = ids.get((Path(frm["uri"]).name, frm["selectionRange"]["start"]["line"], frm["name"]))
                if source is None:
                    source = f"m:{Path(frm['uri']).name}"
                    if not any(e["data"].get("id") == source for e in elements):
                        elements.append(
                            {
                                "data": {
                                    "id": source,
                                    "label": f"{frm['name']}\n{KIND.get(frm['kind'], frm['kind'])} {frm['kind']}",
                                    "parent": f"f:{Path(frm['uri']).name}",
                                }
                            }
                        )
                ranges = ", ".join(
                    f"{r['start']['line'] + 1}:{r['start']['character'] + 1}" for r in call["fromRanges"]
                )
                elements.append(
                    {
                        "data": {
                            "source": source,
                            "target": target,
                            "label": f"fromRanges {len(call['fromRanges'])}: {ranges}",
                        }
                    }
                )
    return {"elements": elements, "layout": {"name": "dagre", "rankDir": "LR", "rankSep": 120}, "height": 560}, counts


# --------------------------------------------------------------------------- SCIP


def short(symbol: str) -> str:
    """The descriptor chain without scheme or package, with a dotted namespace cut to its last two parts.

    The namespace is kept rather than dropped, because one module spelled two ways is a finding.
    """
    if symbol.startswith("local "):
        return symbol
    descriptors = symbol.split(" ", 4)[-1]
    return re.sub(
        r"^`([^`]*)`/",
        lambda m: "`" + ".".join(m.group(1).split(".")[-2:] if m.group(1).count(".") > 3 else [m.group(1)]) + "`/",
        descriptors,
    )


def label_for(symbol: str, doc: str) -> str:
    return f"{symbol} in {doc}" if symbol.startswith("local ") else clip(short(symbol), 44)


def clip(text: str, width: int) -> str:
    """Keep the end of a long symbol, where the distinguishing descriptor is."""
    return text if len(text) <= width else "..." + text[-(width - 3) :]


def scip(spec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    """Every occurrence in every document, joined to the symbol string it names."""
    dump = json.loads(need(DUMPS / spec["scip"]).read_text())

    # A `local N` symbol is private to one document, so the same string in two documents is two symbols.
    def ident(doc: str, symbol: str) -> str:
        return f"{doc}#{symbol}" if symbol.startswith("local ") else symbol

    local = {ident(d["relative_path"], s["symbol"]) for d in dump["documents"] for s in d["symbols"]}
    local |= {
        ident(d["relative_path"], o["symbol"])
        for d in dump["documents"]
        for o in d["occurrences"]
        if o["symbol"].startswith("local ")
    }
    elements: list[dict[str, Any]] = [
        {"data": {"id": "sym", "label": "symbols defined here", "category": ROLE["symbols"]}},
        {"data": {"id": "ext", "label": "symbols from elsewhere", "category": ROLE["external"]}},
    ]
    counts = {"occurrences": 0, "symbols": len(local), "external": 0}
    placed = set()
    for doc in dump["documents"]:
        # No document boxes: dagre overlaps two compounds whose children all point into a third.
        for i, occ in enumerate(doc["occurrences"]):
            counts["occurrences"] += 1
            r = occ["range"]
            oid = f"o:{doc['relative_path']}:{i}"
            elements.append(
                {
                    "data": {
                        "id": oid,
                        "label": f"{doc['relative_path']} {r[0] + 1}:{r[1] + 1}, "
                        + ("+".join(occ["roles"]) if occ["roles"] else "roles 0"),
                    }
                }
            )
            key = ident(doc["relative_path"], occ["symbol"])
            sid = f"s:{key}"
            if sid not in placed:
                home = "sym" if key in local else "ext"
                counts["external"] += home == "ext"
                elements.append(
                    {
                        "data": {
                            "id": sid,
                            "label": label_for(occ["symbol"], doc["relative_path"]),
                            "parent": home,
                            "variant": "alt",
                        }
                    }
                )
                placed.add(sid)
            edge = {"source": oid, "target": sid}
            if "Definition" not in occ["roles"]:
                edge["style"] = "dashed"
            elements.append({"data": edge})
    nodes = sum(1 for e in elements if "source" not in e["data"])
    return {
        "elements": elements,
        "layout": {"name": "dagre", "rankDir": "LR", "rankSep": 260, "nodeSep": 3},
        "height": max(560, nodes * 16),
    }, counts


# --------------------------------------------------------------------------- the page's charts


def sizes(fixture: str, bars: list[tuple[str, str, int]]) -> dict[str, Any]:
    providers = list(dict.fromkeys(p for p, _, _ in bars))
    data = []
    for p in providers:
        rows = [(label, v) for q, label, v in bars if q == p]
        data.append(
            {
                "type": "bar",
                "orientation": "h",
                "name": p,
                "y": [f"{p}: {label}" for label, _ in rows],
                "x": [v for _, v in rows],
                "text": [str(v) for _, v in rows],
                "textposition": "outside",
                "cliponaxis": False,
            }
        )
    return {
        "data": data,
        "height": 60 + 34 * len(bars),
        "layout": {
            "xaxis": {"type": "log", "title": {"text": "count, log scale"}},
            "yaxis": {"autorange": "reversed", "automargin": True},
            "barmode": "overlay",
            "showlegend": False,
            "margin": {"l": 10, "r": 60, "t": 10, "b": 50},
        },
    }


def variants(census: dict[str, int]) -> dict[str, Any]:
    order = [
        "scope",
        "push_symbol",
        "pop_symbol",
        "push_scoped_symbol",
        "pop_scoped_symbol",
        "drop_scopes",
        "jump_to_scope",
        "root",
    ]
    return {
        "data": [
            {
                "type": "bar",
                "x": order,
                "y": [census.get(k, 0) for k in order],
                "text": [str(census.get(k, 0)) for k in order],
                "textposition": "outside",
                "cliponaxis": False,
            }
        ],
        "height": 360,
        "layout": {"yaxis": {"type": "log", "title": {"text": "nodes, log scale"}}, "margin": {"t": 20, "b": 90}},
    }


def main() -> None:
    for fixture, spec in FIXTURES.items():
        print(fixture)
        cst_graph, cst_counts = cst(fixture, spec)
        write(f"{fixture}-ts-cst.json", cst_graph)
        write(f"{fixture}-ts-callgraph.json", extractor(fixture, spec))
        ts = json.loads(need(DUMPS / spec["ts"]).read_text())

        g = sg_graph(spec)
        census = sg_census(g)
        write(f"{fixture}-sg-variants.json", variants(census))
        lsp_graph, lsp_counts = lsp(spec)
        write(f"{fixture}-lsp.json", lsp_graph)
        callables = {n["name"] for n in ts["nodes"]} | {n["cls"] for n in ts["nodes"] if n["cls"]}
        dump = json.loads((DUMPS / spec["lsp"]).read_text())
        callables |= {ch["prepared"]["name"] for f in dump["files"].values() for ch in f["call_hierarchy"]}
        refs_graph, answers = sg_references(fixture, spec, g, callables)
        write(f"{fixture}-sg-references.json", refs_graph)
        path_graph = sg_path(fixture, spec, g, answers)
        print(f"  replayed path: {path_graph.pop('_path_nodes')} nodes, folded to {path_graph.pop('_runs')}")
        write(f"{fixture}-sg-path.json", path_graph)
        scip_graph, scip_counts = scip(spec)
        write(f"{fixture}-scip.json", scip_graph)

        write(
            f"{fixture}-sizes.json",
            sizes(
                fixture,
                [
                    ("tree-sitter", "syntax nodes", cst_counts["all"]),
                    ("tree-sitter", "named syntax nodes", cst_counts["named"]),
                    ("treesitter.py", "callables", len(ts["nodes"])),
                    ("treesitter.py", "call edges", len(ts["edges"])),
                    ("stack-graphs", "graph nodes", len(g["nodes"])),
                    ("stack-graphs", "graph edges", len(g["edges"])),
                    ("LSP", "document symbols", lsp_counts["symbols"]),
                    ("LSP", "call hierarchy items", lsp_counts["items"]),
                    ("LSP", "incoming calls", lsp_counts["incoming"]),
                    ("LSP", "fromRanges", lsp_counts["fromRanges"]),
                    ("SCIP", "occurrences", scip_counts["occurrences"]),
                    ("SCIP", "symbols defined here", scip_counts["symbols"]),
                    ("SCIP", "symbols from elsewhere", scip_counts["external"]),
                ],
            ),
        )


if __name__ == "__main__":
    main()
