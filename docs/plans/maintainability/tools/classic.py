#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# ///
"""Run the classic per-unit complexity metrics over every rearrangement.

The point is not to rank the tools. It is to test one prediction.

README.md argues that a gate on cyclomatic complexity has no floor, because
extraction is subdivision and subdivision lowers every per-unit count for free.
If that is right, then the `extract` transform, which adds single-caller
wrappers and changes nothing a program does, must LOWER cyclomatic complexity.
And the filing transforms, which move code between folders, must leave it
exactly unchanged.

Four tools, because they disagree by a factor of eight on this codebase:

  ruff C901   mccabe 0.7.0. No handler for ternaries, comprehensions or and/or.
  radon       a fuller cyclomatic count.
  lizard      cyclomatic again, plus NLOC and token count, and it speaks
              TypeScript, which the other three do not.
  complexipy  cognitive complexity, which weights nesting rather than counting
              branches, so it is the one that should behave differently.

Usage: classic.py <dir> [<dir> ...] [--label NAME]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def sh(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
    return r.returncode, r.stdout + r.stderr


def ruff_c901(path: Path, cap: int = 10) -> dict:
    """Violations of max-complexity, and the count of functions inspected."""
    code, out = sh(["uvx", "ruff", "check", str(path), "--select", "C901",
                    "--config", f"lint.mccabe.max-complexity={cap}",
                    "--output-format", "json", "--no-cache"])
    try:
        items = json.loads(out)
    except json.JSONDecodeError:
        return {"c901_over": None, "c901_max": None}
    scores = []
    for it in items:
        m = re.search(r"complexity of (\d+)", it.get("message", ""))
        if m:
            scores.append(int(m.group(1)))
    return {"c901_over": len(items), "c901_max": max(scores) if scores else 0}


def radon_cc(path: Path) -> dict:
    code, out = sh(["uvx", "radon", "cc", str(path), "--json"])
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {"radon_n": None}
    scores = [b["complexity"] for blocks in data.values()
              if isinstance(blocks, list) for b in blocks if b.get("type") in ("function", "method")]
    if not scores:
        return {"radon_n": 0, "radon_mean": None, "radon_max": None, "radon_total": 0}
    return {"radon_n": len(scores), "radon_mean": round(sum(scores) / len(scores), 2),
            "radon_max": max(scores), "radon_total": sum(scores)}


def lizard_cc(path: Path) -> dict:
    code, out = sh(["uvx", "lizard", str(path), "--csv"])
    rows = [ln.split(",") for ln in out.strip().splitlines() if ln and ln[0].isdigit()]
    if not rows:
        return {"lizard_n": 0}
    nloc = [int(r[0]) for r in rows]
    ccn = [int(r[1]) for r in rows]
    tok = [int(r[2]) for r in rows]
    return {"lizard_n": len(rows), "lizard_mean": round(sum(ccn) / len(ccn), 2),
            "lizard_max": max(ccn), "lizard_total": sum(ccn),
            "nloc_mean": round(sum(nloc) / len(nloc), 1), "nloc_max": max(nloc),
            "tokens": sum(tok)}


def complexipy_cog(path: Path) -> dict:
    out_file = REPO / "tmp" / "conductance" / "_complexipy.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    sh(["uvx", "complexipy", str(path), "--output", str(out_file),
        "--output-format", "json", "--quiet", "true", "--ignore-complexity", "true"])
    if not out_file.exists():
        return {"cog_n": None}
    try:
        data = json.loads(out_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"cog_n": None}
    funcs = data.get("functions") if isinstance(data, dict) else data
    if not isinstance(funcs, list) or not funcs:
        return {"cog_n": 0, "cog_mean": None, "cog_max": None, "cog_total": 0}
    scores = [f.get("complexity", 0) for f in funcs]
    return {"cog_n": len(scores), "cog_mean": round(sum(scores) / len(scores), 2),
            "cog_max": max(scores), "cog_total": sum(scores)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--out", default="classic.json")
    args = ap.parse_args()

    rows = []
    for d in args.dirs:
        p = REPO / d
        if not p.exists():
            continue
        label = Path(d).name
        meta = p / "_experiment.json"
        note = json.loads(meta.read_text())["transform"] if meta.exists() else "source"
        is_py = any(p.rglob("*.py"))
        row = {"dir": d, "label": label, "transform": note, **lizard_cc(p)}
        if is_py:
            row |= ruff_c901(p) | radon_cc(p) | complexipy_cog(p)
        rows.append(row)
        print(f"  measured {label} ({note})")

    dest = REPO / "tmp" / "conductance" / args.out
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    hdr = (f"{'variant':<18} {'funcs':>6} {'C901>10':>8} {'radon mu':>9} {'radon max':>10} "
           f"{'lizard mu':>10} {'cog mu':>7} {'cog max':>8} {'NLOC mu':>8} {'tokens':>8}")
    print(f"\n{hdr}\n" + "-" * len(hdr))
    for r in rows:
        print(f"{r['transform']:<18} {str(r.get('radon_n', r.get('lizard_n'))):>6} "
              f"{str(r.get('c901_over', '-')):>8} {str(r.get('radon_mean', '-')):>9} "
              f"{str(r.get('radon_max', '-')):>10} {str(r.get('lizard_mean', '-')):>10} "
              f"{str(r.get('cog_mean', '-')):>7} {str(r.get('cog_max', '-')):>8} "
              f"{str(r.get('nloc_mean', '-')):>8} {str(r.get('tokens', '-')):>8}")
    print(f"\nwrote {dest.relative_to(REPO)}")


if __name__ == "__main__":
    main()
