"""Extractors a golden comparison names: what a markdown or mermaid artifact is made of.

A facet's ``extract`` is any ``str -> object`` (ADR 0046), so nothing here is privileged.
These are the ones the shipped cases need, kept in one place because they are the part
that is easy to get subtly wrong -- a node-id regex that also matches ``classDef``, a
fence matcher that stops at the first ``</details>``.

Every extractor is pure and free, so a golden comparison is exercised against committed
text in ``tests/test_units.py`` with no rollout and no spend.
"""

from __future__ import annotations

# Standard Library
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Callable

#: A fenced mermaid block; group 1 is its body.
MERMAID_FENCE = re.compile(r"```mermaid[^\n]*\n(.*?)```", re.DOTALL)
#: An ATX heading of any level; group 1 is the level, group 2 the text.
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
#: One flowchart identifier.
_ID = r"[A-Za-z][A-Za-z0-9_]*"
#: The shape a node id may carry: ``[label]``, ``(label)``, ``{label}``, and their doubles.
_SHAPE = r"(?:\[\[?[^\]]*\]\]?|\(\(?[^)]*\)\)?|\{[^}]*\})?"
#: An inline class assignment: ``Node:::className``.
_INLINE_CLASS = r"(?::::[A-Za-z0-9_]+)?"
#: A link between two nodes: ``-->``, ``---``, ``-.->``, ``==>``, ``--o``, ``<-->``.
_ARROW = r"<?[-=.]{2,}[>ox]?"
#: A node declaration: an id immediately followed by a shape.
_NODE = re.compile(rf"(?:^|[\s>|])({_ID})\s*(?:\[|\(|\{{)")
#: An edge, in either direction, past whatever shape or class its endpoints carry.
#:
#: The endpoints are the part that is easy to get wrong: ``Loader[Load CSV] --> Transform``
#: has a ``]`` between the id and the arrow, and ``Transform:::io --> Report`` has a class
#: name that a looser pattern collects as a node of its own.
_EDGE = re.compile(rf"({_ID}){_SHAPE}{_INLINE_CLASS}\s*{_ARROW}(?:\|[^|]*\|)?\s*({_ID})")
#: A ``classDef`` line; group 1 is the class name, group 2 its style body.
_CLASSDEF = re.compile(r"^\s*classDef\s+([A-Za-z0-9_]+)\s+(.+?)\s*$", re.MULTILINE)
#: Any ``#rgb`` or ``#rrggbb`` colour literal.
_HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")

# Mermaid keywords that the node pattern would otherwise collect as node ids.
_KEYWORDS = frozenset(
    {
        "flowchart",
        "graph",
        "subgraph",
        "end",
        "classDef",
        "class",
        "style",
        "linkStyle",
        "click",
        "direction",
        "sequenceDiagram",
        "stateDiagram",
        "erDiagram",
        "gantt",
        "pie",
        "journey",
        "participant",
        "note",
        "loop",
        "alt",
        "opt",
        "par",
        "rect",
    }
)


def fences(doc: str) -> list[str]:
    """Every mermaid fence body, in document order."""
    return MERMAID_FENCE.findall(doc)


def fence_count(doc: str) -> int:
    """How many mermaid fences the document has."""
    return len(fences(doc))


def visible_fences(doc: str) -> list[str]:
    """Fence bodies that are *not* inside a ``<details>`` block.

    Depth is counted from the text before each fence rather than by splitting on
    ``</details>``, so a document with two collapsed blocks reports both correctly.
    """
    out = []
    for match in MERMAID_FENCE.finditer(doc):
        before = doc[: match.start()]
        if before.count("<details") <= before.count("</details>"):
            out.append(match.group(1))
    return out


def collapsed_fences(doc: str) -> list[str]:
    """Fence bodies that sit inside a ``<details>`` block."""
    visible = visible_fences(doc)
    seen = list(visible)
    out = []
    for body in fences(doc):
        if body in seen:
            seen.remove(body)
        else:
            out.append(body)
    return out


def node_ids(doc: str) -> set[str]:
    """Every flowchart node id across the document's fences, keywords excluded.

    The concept set of a diagram: what it is *about*, independent of the labels and the
    layout. Usually the facet with the tightest defensible tolerance, because a fixture
    fixes the things that exist even when it leaves their names free.
    """
    ids: set[str] = set()
    for body in fences(doc):
        ids.update(_NODE.findall(body))
        for left, right in _EDGE.findall(body):
            ids.update((left, right))
    return ids - _KEYWORDS


def edges(doc: str) -> set[str]:
    """Every ``a->b`` pair across the document's fences, as ``"a->b"`` strings.

    The diagram's shape rather than its contents: two diagrams over the same nodes with
    different edges are telling different stories.
    """
    out: set[str] = set()
    for body in fences(doc):
        out.update(f"{left}->{right}" for left, right in _EDGE.findall(body) if left not in _KEYWORDS)
    return out


def classdef_names(doc: str) -> set[str]:
    """Every ``classDef`` selector declared across the fences."""
    return {name for name, _ in _CLASSDEF.findall(doc)}


def classdef_count(doc: str) -> int:
    """How many ``classDef`` lines the document declares."""
    return len(_CLASSDEF.findall(doc))


def fill_colours(doc: str) -> set[str]:
    """Every ``fill:`` colour a ``classDef`` sets, lowercased."""
    return _styled_colours(doc, "fill")


def text_colours(doc: str) -> set[str]:
    """Every ``color:`` colour a ``classDef`` sets, lowercased."""
    return _styled_colours(doc, "color")


def _styled_colours(doc: str, key: str) -> set[str]:
    """The colours one ``classDef`` property carries, across every fence."""
    pattern = re.compile(rf"(?<![-\w]){key}\s*:\s*(#[0-9a-fA-F]{{3,6}})")
    return {c.lower() for _, body in _CLASSDEF.findall(doc) for c in pattern.findall(body)}


def unstyled_nodes(doc: str) -> set[str]:
    """Node ids that no ``class`` statement and no inline ``:::`` shorthand assigns a class to.

    The palette mandate's actual claim: not "a classDef exists" but "no node was left on
    Mermaid's default". A document can declare one ``classDef``, apply it to a single node,
    and satisfy every substring check ever written about it.
    """
    assigned: set[str] = set()
    for body in fences(doc):
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("class ") and len(stripped.split()) >= 3:
                assigned.update(part.strip() for part in stripped.split()[1].split(","))
        assigned.update(re.findall(r"([A-Za-z][A-Za-z0-9_]*)\s*(?:\[[^\]]*\]|\([^)]*\))?:::", body))
    return node_ids(doc) - assigned - _KEYWORDS


def headings(doc: str) -> set[str]:
    """Every ATX heading's text, whatever its level."""
    return {text.strip() for _, text in HEADING.findall(doc)}


def headings_at(level: int) -> Callable[[str], set[str]]:
    """An extractor for the headings at one level: ``headings_at(2)`` for every ``##``."""

    def extract(doc: str) -> set[str]:
        return {text.strip() for hashes, text in HEADING.findall(doc) if len(hashes) == level}

    return extract


def hex_colours(doc: str) -> set[str]:
    """Every hex colour literal anywhere in the document, lowercased."""
    return {c.lower() for c in _HEX.findall(doc)}


def body_text(doc: str) -> str:
    """The document with its fenced code removed: the prose, for a similarity tolerance."""
    return re.sub(r"```.*?```", "", doc, flags=re.DOTALL).strip()
