#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["tree-sitter>=0.25", "tree-sitter-python>=0.25"]
# ///
"""Materialise behaviour-preserving rearrangements of a codebase, for scoring.

Every transform here changes only where code LIVES, never what it does. The
point is to find which structural choices move a maintainability score and by
how much, so the experiment must hold behaviour fixed.

Two families, and the difference matters:

  filing       moves definitions between files and folders. Because resolution
               is by name, the call graph's EDGES are invariant under these and
               only the PARTITION changes. This isolates the folder hypothesis.
  structural   changes which definitions exist: inlining a single-caller
               function, duplicating a shared one into each caller. These do
               move edges, and they are where real quality signal should live.

Usage:
    experiment.py <transform> --n <N> [--k 4] [--seed 1]

Writes tmp/exp-<N>-pytest-xharness-evals/ and prints the path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]

# Set by main() from --src / --ext so the same transforms run on any tree.
SRC = REPO / "src" / "pytest_xharness_eval"
EXTS = (".py",)
SKIP: list[str] = []


def py_files() -> list[Path]:
    return sorted(
        f for f in SRC.rglob("*")
        if f.is_file() and f.suffix in EXTS and not any(k in str(f) for k in SKIP)
    )


def flat_name(f: Path) -> str:
    """A unique flat filename: parent_stem.py, so nothing collides."""
    rel = f.relative_to(SRC)
    if len(rel.parts) == 1:
        return rel.name
    return f"{'_'.join(rel.parts[:-1])}_{rel.stem}{f.suffix}"


def write(dest_root: Path, rel: str, text: str) -> None:
    p = dest_root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


# ---- filing transforms ----------------------------------------------------


def t_baseline(dest: Path) -> str:
    for f in py_files():
        write(dest, str(f.relative_to(SRC)), f.read_text(encoding="utf-8"))
    return "the tree as it is, the control"


def t_flatten(dest: Path) -> str:
    for f in py_files():
        write(dest, flat_name(f), f.read_text(encoding="utf-8"))
    return "every module in one folder, no subdirectories"


def t_single(dest: Path) -> str:
    parts = [f"# ---- {f.relative_to(SRC)} ----\n{f.read_text(encoding='utf-8')}" for f in py_files()]
    write(dest, f"everything{EXTS[0]}", "\n\n".join(parts))
    return "every module concatenated into one file"


def t_random(dest: Path, k: int, seed: int) -> str:
    rng = random.Random(seed)
    for f in py_files():
        bucket = f"pkg{rng.randrange(k)}"
        write(dest, f"{bucket}/{flat_name(f)}", f.read_text(encoding="utf-8"))
    return f"every module assigned to one of {k} folders at random"


def t_alpha(dest: Path) -> str:
    # The ORIGINAL stem, not the flattened name. Flattened names carry the
    # parent folder as a prefix, so grouping those by first letter silently
    # reconstructs the declared architecture and is no control at all.
    for f in py_files():
        write(dest, f"grp_{f.stem[0].lower()}/{flat_name(f)}", f.read_text(encoding="utf-8"))
    return "folders by first letter of the original filename, a boundary with no meaning"


def t_hash(dest: Path, k: int) -> str:
    """Deterministic pseudo-random: same shape as random, no seed sensitivity."""
    for f in py_files():
        h = int(hashlib.sha1(flat_name(f).encode()).hexdigest(), 16)
        write(dest, f"pkg{h % k}/{flat_name(f)}", f.read_text(encoding="utf-8"))
    return f"every module hashed into one of {k} folders"


def t_onefile_per_folder(dest: Path) -> str:
    """Keep the declared folders, collapse each to a single module."""
    groups: dict[str, list[Path]] = defaultdict(list)
    for f in py_files():
        rel = f.relative_to(SRC)
        groups[rel.parts[0] if len(rel.parts) > 1 else "_root"].append(f)
    for name, files in groups.items():
        body = "\n\n".join(f"# ---- {f.relative_to(SRC)} ----\n{f.read_text(encoding='utf-8')}" for f in files)
        write(dest, f"{name}{EXTS[0]}", body)
    return "the declared folders kept, each collapsed to one module"


def t_split(dest: Path) -> str:
    """One file per top-level definition, folders preserved."""
    import tree_sitter_python as tsp
    from tree_sitter import Language, Parser

    parser = Parser(Language(tsp.language()))
    for f in py_files():
        src = f.read_bytes()
        tree = parser.parse(src)
        rel = f.relative_to(SRC)
        stem_dir = rel.parent / rel.stem
        header, chunks = [], []
        for child in tree.root_node.children:
            text = src[child.start_byte : child.end_byte].decode("utf-8", "replace")
            if child.type in ("function_definition", "class_definition", "decorated_definition"):
                chunks.append(text)
            else:
                header.append(text)
        if not chunks:
            write(dest, str(rel), f.read_text(encoding="utf-8"))
            continue
        preamble = "\n".join(header)
        for i, chunk in enumerate(chunks):
            write(dest, str(stem_dir / f"part{i:02d}{f.suffix}"), f"{preamble}\n\n{chunk}\n")
    return "one file per top-level definition"


def t_leiden(dest: Path, graph: Path) -> str:
    """Folders replaced by the communities the call graph itself implies."""
    data = json.loads(graph.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in data["nodes"]}
    edges = [(e["source"], e["target"]) for e in data["edges"]]

    # Label-propagation: cheap, deterministic enough, no extra dependency.
    label = {nid: i for i, nid in enumerate(nodes)}
    adj: dict[str, list[str]] = defaultdict(list)
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    for _ in range(12):
        for nid in sorted(nodes):
            if not adj[nid]:
                continue
            counts: dict[int, int] = defaultdict(int)
            for nb in adj[nid]:
                counts[label[nb]] += 1
            label[nid] = min(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]

    # A file goes to the community most of its definitions ended up in.
    file_vote: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for nid, n in nodes.items():
        file_vote[n["file"]][label[nid]] += 1
    order = {c: i for i, c in enumerate(sorted({max(v.items(), key=lambda kv: kv[1])[0] for v in file_vote.values()}))}

    for f in py_files():
        rel_repo = str(f.relative_to(REPO))
        votes = file_vote.get(rel_repo)
        comm = order[max(votes.items(), key=lambda kv: kv[1])[0]] if votes else 0
        write(dest, f"c{comm:02d}/{flat_name(f)}", f.read_text(encoding="utf-8"))
    return "folders replaced by the communities the call graph implies"


# ---- structural transforms -------------------------------------------------
# These change WHICH definitions exist, so edges move. They are the family that
# should carry real quality signal, and the family where a metric can be caught
# rewarding something a reviewer would reject.


def t_duplicate(dest: Path, min_callers: int) -> str:
    """Copy every shared function into each file that calls it.

    Objectively worse code: the same logic in many places, drifting apart. But
    it deletes cross-file edges, because a local definition wins name
    resolution. If the score IMPROVES, the metric rewards duplication and
    cannot be used as a target.
    """
    import tree_sitter_python as tsp
    from tree_sitter import Language, Parser

    parser = Parser(Language(tsp.language()))
    defs: dict[str, tuple[Path, str]] = {}
    calls_by_file: dict[Path, set[str]] = defaultdict(set)
    callers: dict[str, set[Path]] = defaultdict(set)

    for f in py_files():
        src = f.read_bytes()
        tree = parser.parse(src)

        def visit(node):
            if node.type == "function_definition" and node.parent.type == "module":
                nm = node.child_by_field_name("name")
                if nm is not None:
                    defs[src[nm.start_byte : nm.end_byte].decode()] = (
                        f, src[node.start_byte : node.end_byte].decode("utf-8", "replace"))
            if node.type == "call":
                fn = node.child_by_field_name("function")
                if fn is not None and fn.type == "identifier":
                    calls_by_file[f].add(src[fn.start_byte : fn.end_byte].decode())
            for c in node.children:
                visit(c)

        visit(tree.root_node)

    for f, names in calls_by_file.items():
        for nm in names:
            if nm in defs and defs[nm][0] != f:
                callers[nm].add(f)

    copied = 0
    for f in py_files():
        text = f.read_text(encoding="utf-8")
        extra = []
        for nm in sorted(calls_by_file.get(f, ())):
            if nm in defs and defs[nm][0] != f and len(callers[nm]) >= min_callers:
                extra.append(f"# ---- copied from {defs[nm][0].relative_to(SRC)} ----\n{defs[nm][1]}")
                copied += 1
        if extra:
            text = text + "\n\n" + "\n\n".join(extra) + "\n"
        write(dest, str(f.relative_to(SRC)), text)
    return f"every function with {min_callers}+ callers copied into each calling file ({copied} copies)"


def t_god_class(dest: Path) -> str:
    """Every module-level function becomes a method on one class, per file."""
    import tree_sitter_python as tsp
    from tree_sitter import Language, Parser

    parser = Parser(Language(tsp.language()))
    for f in py_files():
        src = f.read_bytes()
        tree = parser.parse(src)
        rel = f.relative_to(SRC)
        head, methods, rest = [], [], []
        for child in tree.root_node.children:
            text = src[child.start_byte : child.end_byte].decode("utf-8", "replace")
            if child.type == "function_definition":
                methods.append("\n".join("    " + ln for ln in text.splitlines()))
            elif child.type in ("class_definition", "decorated_definition"):
                rest.append(text)
            else:
                head.append(text)
        body = "\n".join(head) + "\n\n" + "\n\n".join(rest)
        if methods:
            body += "\n\n\nclass God:\n" + "\n\n".join(methods) + "\n"
        write(dest, str(rel), body)
    return "every module-level function folded into one class per file"


def t_inline(dest: Path, graph: Path, max_callers: int) -> str:
    """Delete every definition reached from at most `max_callers` places.

    The opposite move to extraction. A leverage-1 name is one the README calls
    tidying: it costs a name and saves no reading. Removing it should be
    neutral-to-good, and this measures which.

    The body is not spliced into the caller, because the call graph does not
    care where the statements live, only that the name is gone.
    """
    import tree_sitter_python as tsp
    from tree_sitter import Language, Parser

    data = json.loads(graph.read_text(encoding="utf-8"))
    indeg: dict[str, int] = defaultdict(int)
    for e in data["edges"]:
        indeg[e["target"]] += 1
    doomed: dict[str, set[int]] = defaultdict(set)
    for n in data["nodes"]:
        if 0 < indeg[n["id"]] <= max_callers and n.get("cls") is None:
            doomed[n["file"]].add(n["line"])

    parser = Parser(Language(tsp.language()))
    removed = 0
    for f in py_files():
        rel_repo = str(f.relative_to(REPO))
        lines = doomed.get(rel_repo, set())
        src = f.read_bytes()
        if not lines:
            write(dest, str(f.relative_to(SRC)), src.decode("utf-8", "replace"))
            continue
        tree = parser.parse(src)
        keep = []
        for child in tree.root_node.children:
            if child.type == "function_definition" and (child.start_point[0] + 1) in lines:
                removed += 1
                continue
            keep.append(src[child.start_byte : child.end_byte].decode("utf-8", "replace"))
        write(dest, str(f.relative_to(SRC)), "\n".join(keep) + "\n")
    return f"every function with 1..{max_callers} callers deleted ({removed} removed)"


def t_extract(dest: Path, every: int) -> str:
    """Wrap every `every`-th run of statements in a new single-caller function.

    The tidying failure the README names, applied deliberately: names that add
    a boundary and save nobody any reading.
    """
    import tree_sitter_python as tsp
    from tree_sitter import Language, Parser

    parser = Parser(Language(tsp.language()))
    added = 0
    for f in py_files():
        src = f.read_bytes()
        tree = parser.parse(src)
        out, extracted = [], []
        for child in tree.root_node.children:
            text = src[child.start_byte : child.end_byte].decode("utf-8", "replace")
            out.append(text)
            if child.type != "function_definition":
                continue
            body = child.child_by_field_name("body")
            if body is None:
                continue
            stmts = [c for c in body.children if c.is_named]
            for i in range(0, len(stmts) - 1, max(every, 1)):
                added += 1
                name = f"_step_{f.stem}_{added}"
                extracted.append(f"def {name}(*a, **k):\n    return None\n")
                out.append(f"# extracted step {added}\n{name}()\n")
        write(dest, str(f.relative_to(SRC)), "\n".join(out + extracted) + "\n")
    return f"one single-caller helper extracted per {every} statements ({added} added)"


TRANSFORMS = {
    "baseline": lambda d, a: t_baseline(d),
    "flatten": lambda d, a: t_flatten(d),
    "single": lambda d, a: t_single(d),
    "random": lambda d, a: t_random(d, a.k, a.seed),
    "hash": lambda d, a: t_hash(d, a.k),
    "alpha": lambda d, a: t_alpha(d),
    "fold-collapse": lambda d, a: t_onefile_per_folder(d),
    "split": lambda d, a: t_split(d),
    "leiden": lambda d, a: t_leiden(d, a.graph),
    "duplicate": lambda d, a: t_duplicate(d, a.k),
    "god-class": lambda d, a: t_god_class(d),
    "inline": lambda d, a: t_inline(d, a.graph, a.k),
    "extract": lambda d, a: t_extract(d, a.k),
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("transform", choices=sorted(TRANSFORMS))
    ap.add_argument("--n", required=True, help="experiment number, used in the directory name")
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--graph", type=Path, default=REPO / "tmp" / "conductance" / "ts-py.json")
    ap.add_argument("--src", default="src/pytest_xharness_eval")
    ap.add_argument("--ext", default=".py")
    ap.add_argument("--skip", default="")
    args = ap.parse_args()

    global SRC, EXTS, SKIP
    SRC = (REPO / args.src).resolve()
    EXTS = tuple(e.strip() for e in args.ext.split(","))
    SKIP = [k.strip() for k in args.skip.split(",") if k.strip()]

    dest = REPO / "tmp" / f"exp-{args.n}-pytest-xharness-evals"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    note = TRANSFORMS[args.transform](dest, args)
    files = [f for f in dest.rglob("*") if f.is_file() and f.suffix in EXTS]
    folders = {f.parent for f in files}
    (dest / "_experiment.json").write_text(
        json.dumps({"n": args.n, "transform": args.transform, "k": args.k,
                    "seed": args.seed, "note": note,
                    "files": len(files), "folders": len(folders)}, indent=2),
        encoding="utf-8",
    )
    print(f"{dest.relative_to(REPO)}  {args.transform}: {note}")
    print(f"  {len(files)} files in {len(folders)} folders", file=sys.stderr)


if __name__ == "__main__":
    main()
