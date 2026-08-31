#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyYAML>=6.0", "Jinja2>=3.1", "jsonschema>=4.0"]
# ///
"""Render this repository's ADR bundle: authored YAML records -> OKF markdown (ADR 0047).

Vendored from the librarian skill's reference implementation and adapted in two
places for this repository's dialect: the schema sits beside this script, and
`description` is optional (the migrated records carry none, and writing 46 of
them would have been authoring rather than shelving).

    <dir>/NNNN-slug.yml  ->  NNNN-slug.md   OKF-conformant record markdown
                             index.md       OKF reserved directory listing
                             graph.md       companion doc holding the graph
                             graph.json     Cytoscape elements payload

The YAML is the source of truth; every .md and .json emitted here is generated.
Validation runs first and hard: a record that fails the schema stops the build
rather than producing markdown nothing checked.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from jsonschema import Draft202012Validator, FormatChecker

# ── Configuration ───────────────────────────────────────────────────────
SCRIPT = Path(__file__)
SCRIPT_DIR = SCRIPT.parent.resolve()
TEMPLATE_DIR = SCRIPT_DIR / "templates"
DEFAULT_SCHEMA = SCRIPT_DIR / "record.schema.json"

log = logging.getLogger(__name__)

RESERVED_WORDS = {"y", "n", "yes", "no", "true", "false", "on", "off", "null", "~"}

#: Every relation paired with its inverse, so symmetry is checkable.
INVERSE = {
    "extends": "extended_by",
    "extended_by": "extends",
    "split_from": "split_to",
    "split_to": "split_from",
    "supersedes": "superseded_by",
    "superseded_by": "supersedes",
    "tests": "tested_by",
    "tested_by": "tests",
    "depends_on": "depended_on_by",
    "depended_on_by": "depends_on",
    "excepts": "excepted_by",
    "excepted_by": "excepts",
    "see_also": "see_also",
}

#: How each relation reads in generated prose.
PROSE = {
    "extends": "Extends",
    "extended_by": "Extended by",
    "split_from": "Split from",
    "split_to": "Split to",
    "supersedes": "Supersedes",
    "superseded_by": "Superseded by",
    "tests": "Tests",
    "tested_by": "Tested by",
    "depends_on": "Depends on",
    "depended_on_by": "Depended on by",
    "excepts": "Scoped exception to",
    "excepted_by": "Excepted by",
    "see_also": "See also",
}

#: Group colours encode data, not brand, so they stay fixed across themes.
#: Cycled by group order; extend rather than re-map if a repo needs more.
#: Eleven hues spread around the wheel, one per domain, with red deliberately absent:
#: red marks a superseded record, and a group borrowing it would read as a status.
#: Each is >=3.0 against white labels and visible on both the light and dark grounds.
GROUP_COLOURS = [
    "#ea580c",  # orange
    "#a16207",  # gold
    "#4d7c0f",  # lime
    "#059669",  # emerald
    "#0d9488",  # teal
    "#0284c7",  # sky
    "#4f46e5",  # indigo
    "#7c3aed",  # violet
    "#a21caf",  # fuchsia
    "#db2777",  # pink
    "#64748b",  # slate
]
UNGROUPED_COLOUR = "#64748b"

# ── Core ─────────────────────────────────────────────────────────────────


Record = dict[str, Any]


def yamlq(value: Any) -> str:
    """Quote a YAML scalar only where the plain form would be mis-read."""
    text = str(value)
    if (
        text == ""
        or text[0] in ">|*&!%@`-?{}[],#'\"' "
        or text[-1] in ": "
        or ": " in text
        or " #" in text
        or text.lower() in RESERVED_WORDS
        or re.fullmatch(r"[-+]?[\d._eE:]+", text) is not None
    ):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def group_of(record: Record, group_by: str) -> str:
    """The cluster a record belongs to. Explicit `group` always wins."""
    if record.get("group"):
        return str(record["group"])
    if group_by == "plan_id" and record.get("plan_id"):
        return str(record["plan_id"])
    tags = record.get("tags") or []
    return str(tags[0]) if tags else "ungrouped"


def load(source_dir: Path) -> list[Record]:
    """Read every record, newest key order preserved, dates re-stringified.

    YAML resolves an unquoted 2026-08-30 to a date object; templates and the
    JSON payload both want the ISO string back.
    """
    records = []
    for path in sorted(source_dir.glob("*.yml")):
        if path.name == "index.yml":
            continue
        record = yaml.safe_load(path.read_text(encoding="utf-8"))
        for key in ("accepted_on", "last_changed_on"):
            if key in record:
                record[key] = str(record[key])
        records.append(record)
    return records


def validate(records: list[Record], schema_path: Path) -> list[str]:
    """Schema errors as flat strings. Empty means every record conforms."""
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = []
    for record in records:
        # YAML dates survive as objects; JSON Schema tools validate the JSON
        # projection, so make the same projection here.
        as_json = json.loads(json.dumps(record, default=str))
        rid = record.get("id", "<no id>")
        for err in sorted(validator.iter_errors(as_json), key=lambda e: list(e.path)):
            where = "/".join(str(p) for p in err.path) or "<root>"
            errors.append(f"{rid}: {where}: {err.message}")
    return errors


def unresolved(records: list[Record]) -> list[str]:
    """relates_to targets that name a record which does not exist."""
    known = {r["id"] for r in records}
    return [
        f"{r['id']}: relates_to target {e['target']} does not exist"
        for r in records
        for e in r.get("relates_to", [])
        if e["target"] not in known
    ]


def asymmetries(records: list[Record]) -> list[Record]:
    """Edges whose inverse is absent on the far record.

    Reported, never failed: a one-way relation is a gap in the record set, and
    whether to close it is the maintainer's call.
    """
    by_id = {r["id"]: r for r in records}
    out = []
    for record in records:
        for edge in record.get("relates_to", []):
            target = by_id.get(edge["target"])
            if target is None:
                continue
            want = INVERSE[edge["relation"]]
            back = target.get("relates_to", [])
            if not any(b["target"] == record["id"] and b["relation"] == want for b in back):
                out.append(
                    {
                        "source": record["id"],
                        "relation": edge["relation"],
                        "target": edge["target"],
                        "inverse": want,
                    }
                )
    return out


def cytoscape(records: list[Record], group_by: str) -> Record:
    """Cytoscape elements: records as child nodes inside compound group nodes."""
    groups = sorted({group_of(r, group_by) for r in records})
    colour = {
        g: (UNGROUPED_COLOUR if g == "ungrouped" else GROUP_COLOURS[i % len(GROUP_COLOURS)])
        for i, g in enumerate(groups)
    }
    elements: list[Record] = [{"data": {"id": f"group-{g}", "label": g, "colour": colour[g]}} for g in groups]
    for record in records:
        group = group_of(record, group_by)
        elements.append(
            {
                "data": {
                    "id": record["id"],
                    "label": record["id"].split("-")[-1],
                    "parent": f"group-{group}",
                    "colour": colour[group],
                    "file": f"{record['id'].split('-')[-1]}-{record['slug']}.md",
                    "title": record["title"],
                    "description": record.get("description", record["title"]),
                    "status": record["status"],
                    "group": group,
                    "tags": ", ".join(record.get("tags", [])),
                }
            }
        )
    seen: set[str] = set()
    for record in records:
        for edge in record.get("relates_to", []):
            eid = f"{record['id']}-{edge['relation']}-{edge['target']}"
            if eid in seen:
                continue
            seen.add(eid)
            elements.append(
                {
                    "data": {
                        "id": eid,
                        "source": record["id"],
                        "target": edge["target"],
                        "label": edge["relation"].replace("_", " "),
                        "relation": edge["relation"],
                        "note": edge.get("note", ""),
                    }
                }
            )
    return {"elements": elements, "layout": {"name": "cose"}, "height": 620}


def strip_frontmatter(text: str) -> str:
    """A generated record without its YAML frontmatter: the reading surface only."""
    if not text.startswith("---"):
        return text
    return text.split("\n---\n", 1)[-1].lstrip("\n")


def embed(payload: Any) -> str:
    """JSON for a <script> block. `</` is escaped so a body cannot close the tag."""
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


def design_tokens() -> Record:
    """The repository's shipped design tokens, so the viewer matches the report page.

    Falls back to an empty mapping when the asset is absent (the bundle stays
    renderable outside this repository); the template then uses its own defaults.
    """
    asset = SCRIPT_DIR.parents[1] / "src" / "pytest_xharness_eval" / "assets" / "report.tokens.json"
    try:
        return json.loads(asset.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def verify_page(html: str, expected_records: int) -> None:
    """The viewer's embedded payloads must survive the trip into the document.

    Checked at build time because the failure is silent otherwise: a record body
    containing `</script>` truncates its data block, and the page then renders a graph
    that is quietly missing records. Parsing each block back is the only proof that the
    escaping held.
    """
    for block, expected in (("graph-data", None), ("record-data", expected_records), ("token-data", None)):
        found = re.search(rf'<script id="{block}" type="application/json">(.*?)</script>', html, re.S)
        if not found:
            raise ValueError(f"graph.html: the {block} block is missing")
        try:
            payload = json.loads(found.group(1).replace("<\\/", "</"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"graph.html: the {block} block does not parse: {exc}") from exc
        if expected is not None and len(payload) != expected:
            raise ValueError(
                f"graph.html: the {block} block holds {len(payload)} entries, expected {expected}; "
                "a record body most likely closed the script tag it was embedded in"
            )


def environment(by_id: dict[str, Record]) -> Environment:
    """Jinja environment. StrictUndefined so a missing field fails loudly."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
    )
    env.filters["yamlq"] = yamlq
    env.filters["blockquote"] = lambda s: s.replace("\n", "\n> ")
    env.filters["relation_prose"] = lambda r: PROSE[r]
    env.filters["record_link"] = lambda i: f"{i.split('-')[-1]}-{by_id[i]['slug']}.md"
    env.filters["oneline"] = lambda s: " ".join(str(s).split())
    return env


def render(
    source_dir: Path,
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    group_by: str = "tag",
    author: str = "human:maintainer",
) -> Record:
    """Generate the bundle. Raises ValueError if any record fails validation."""
    records = load(source_dir)
    if not records:
        raise ValueError(f"no records found in {source_dir}")

    problems = validate(records, schema_path) + unresolved(records)
    if problems:
        raise ValueError("records did not validate:\n  " + "\n  ".join(problems))

    by_id = {r["id"]: r for r in records}
    env = environment(by_id)

    for record in records:
        name = f"{record['id'].split('-')[-1]}-{record['slug']}.md"
        (source_dir / name).write_text(
            env.get_template("record.md.j2").render(rec=record, author=author),
            encoding="utf-8",
        )

    edges = [
        {"source": r["id"], "relation": e["relation"], "target": e["target"]}
        for r in records
        for e in r.get("relates_to", [])
    ]
    groups = [
        (g, [r for r in records if group_of(r, group_by) == g])
        for g in sorted({group_of(r, group_by) for r in records})
    ]
    (source_dir / "index.md").write_text(
        env.get_template("index.md.j2").render(records=records, areas=groups, edges=edges),
        encoding="utf-8",
    )

    graph = cytoscape(records, group_by)
    (source_dir / "graph.json").write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    skew = asymmetries(records)
    (source_dir / "graph.md").write_text(
        env.get_template("graph.md.j2").render(
            node_count=len(records),
            edge_count=len(edges),
            group_count=len(groups),
            asymmetries=skew,
        ),
        encoding="utf-8",
    )
    # The browsable viewer. Self-contained on purpose: the graph payload and every
    # record's markdown are embedded, so the page opens from the filesystem with a
    # double-click and needs no server, exactly as the report page does (ADR 0028).
    # `</` is escaped because a record body containing `</script>` would otherwise
    # close the tag it is embedded in.
    bodies = {
        r["id"]: {
            "file": f"{r['id'].split('-')[-1]}-{r['slug']}.md",
            "title": r["title"],
            "status": r["status"],
            "status_note": r.get("status_note", ""),
            "markdown": strip_frontmatter((source_dir / f"{r['id'].split('-')[-1]}-{r['slug']}.md").read_text(encoding="utf-8")),
        }
        for r in records
    }
    page = env.get_template("graph.html.j2").render(
        graph_json=embed(graph),
        records_json=embed(bodies),
        tokens_json=embed(design_tokens()),
        node_count=len(records),
        edge_count=len(edges),
        asymmetry_count=len(skew),
    )
    verify_page(page, len(records))
    (source_dir / "graph.html").write_text(page, encoding="utf-8")

    return {
        "records": len(records),
        "edges": len(edges),
        "groups": len(groups),
        "asymmetries": skew,
        "elements": len(graph["elements"]),
    }


# ── CLI ──────────────────────────────────────────────────────────────────


def main(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s", stream=sys.stderr
    )
    try:
        result = render(
            args.directory,
            schema_path=args.schema,
            group_by=args.group_by,
            author=args.author,
        )
    except ValueError as exc:
        log.error("%s", exc)
        return 1

    log.info(
        "rendered %d records, %d edges, %d groups (%d graph elements)",
        result["records"],
        result["edges"],
        result["groups"],
        result["elements"],
    )
    for skew in result["asymmetries"]:
        log.info(
            "  one-way: %s --%s--> %s (no '%s' back-edge)",
            skew["source"],
            skew["relation"],
            skew["target"],
            skew["inverse"],
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("directory", type=Path, help="bundle directory holding the .yml records")
    parser.add_argument(
        "--schema", type=Path, default=DEFAULT_SCHEMA, help="record schema (default: the skill's own)"
    )
    parser.add_argument(
        "--group-by",
        choices=["tag", "plan_id"],
        default="tag",
        help="graph clustering key when a record has no explicit group",
    )
    parser.add_argument(
        "--author", default="human:maintainer", help="value for the generated frontmatter's generated.by"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(build_parser().parse_args()))
