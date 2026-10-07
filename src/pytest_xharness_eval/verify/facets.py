"""Extractors a golden comparison names: what a markdown or mermaid artifact is made of.

A facet's ``extract`` is any ``str -> object`` (ADR 0046), so nothing here is privileged.
These are the ones the shipped cases need, kept in one place because they are the part
that is easy to get subtly wrong -- a node-id regex that also matches ``classDef``, a
fence matcher that stops at the first ``</details>``.

Every extractor is pure and free, so a golden comparison is exercised against committed
text in ``tests/verify/test_facets.py`` with no rollout and no spend.
"""

from __future__ import annotations

# Standard Library
import itertools
import re
from dataclasses import dataclass, field
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
#: A link between two nodes once its label is gone: ``-->``, ``---``, ``-.->``, ``==>``,
#: ``--o``, ``--x``, ``<-->``, ``~~~``.
_ARROW = r"<?(?:-{2,}|={2,}|-\.+-|~{3,})[>ox]?"
#: What a flowchart statement is made of once its labels are gone: an id with its optional
#: ``:::class``, an arrow, or the ``&`` that joins several ids on one side of an arrow.
_TOKEN = re.compile(rf"({_ID})(?::::([A-Za-z0-9_]+))?|({_ARROW})|&")
#: An edge's ``|label|``.
_PIPE_LABEL = re.compile(r"\|[^|]*\|")
#: An edge's inline label, ``-- text -->``, ``== text ==>`` or ``-. text .->``, which
#: a looser reading collects as nodes of their own. The opener is never part of an arrow.
_EDGE_TEXT = re.compile(
    r"(?<![-=.<])(?:--|==|-\.)(?![->=.]|[ox]\s)\s*[^-=.>\s][^>]*?\s*(-{2,}>|={2,}>|\.-+>|-{3,}|={3,}|-{2,}[ox]\b|\.-+)"
)
#: A diagram's YAML front matter (``---`` / ``config: ...`` / ``---``), whose keys are not ids.
_FRONT_MATTER = re.compile(r"\A\s*---\s*\n.*?\n\s*---\s*(?:\n|\Z)", re.DOTALL)
#: A fence that holds a flowchart: its header line names one.
_FLOWCHART = re.compile(r"^\s*(?:flowchart|graph)\b", re.MULTILINE)
#: Statements that declare no node and no edge.
_NOT_A_NODE = frozenset({"flowchart", "graph", "classDef", "style", "linkStyle", "click", "direction", "end"})
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


@dataclass(slots=True)
class _Flowchart:
    """What one flowchart fence declares, read statement by statement."""

    nodes: set[str] = field(default_factory=set)
    edges: set[tuple[str, str]] = field(default_factory=set)
    classed: set[str] = field(default_factory=set)
    containers: set[str] = field(default_factory=set)


def _skip_shape(line: str, i: int) -> int:
    """The index just past the balanced shape opening at ``i``, quotes respected.

    Every node shape nests its delimiters: ``[[sub]]``, ``((circle))``, ``{{hex}}``,
    ``[(cylinder)]``, ``([stadium])``. Counting depth across all three bracket kinds reads
    each one whole, where a single-pair pattern stops at the first closer (issue #3).
    """
    depth, quoted = 0, False
    while i < len(line):
        c = line[i]
        if c == '"':
            quoted = not quoted
        elif not quoted and c in "[({":
            depth += 1
        elif not quoted and c in "])}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return i


def _without_shapes(line: str) -> str:
    """The statement with every node's shape and label removed, ids and ``:::`` kept."""
    out: list[str] = []
    i = 0
    while i < len(line):
        c = line[i]
        after_id = bool(out) and (out[-1].rstrip()[-1:].isalnum() or out[-1].rstrip()[-1:] == "_")
        if c in "[({" and after_id:
            i = _skip_shape(line, i)
        elif c == ">" and after_id and out[-1][-1:] not in "-=.":
            # The asymmetric shape, ``A>label]``.
            close = line.find("]", i)
            i = len(line) if close < 0 else close + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _read(body: str) -> _Flowchart | None:
    """Read one fence as a flowchart, or ``None`` when it holds another kind of diagram.

    Comments, labels and edge text are removed before anything is read as an id, so a word
    inside a ``%%`` comment, a ``[[label]]`` or a ``-. label .->`` never becomes a node.
    A ``subgraph`` id is a container, not a node.
    """
    if not _FLOWCHART.search(body):
        return None
    chart = _Flowchart()
    for text in _statements(body):
        head, _, rest = text.partition(" ")
        if head in _NOT_A_NODE:
            continue
        if head == "class":
            ids, _, cls = rest.strip().partition(" ")
            if cls.strip():
                chart.classed.update(part.strip() for part in ids.split(","))
        elif head == "subgraph":
            found = re.match(_ID, _without_shapes(rest.strip()))
            if found:
                chart.containers.add(found.group(0))
        else:
            _read_statement(_EDGE_TEXT.sub(" --> ", _without_shapes(_PIPE_LABEL.sub(" ", text))), chart)
    chart.nodes -= chart.containers | _KEYWORDS
    return chart


def _statements(body: str) -> list[str]:
    """Every statement of a fence: front matter and ``%%`` comment lines dropped, ``;`` split."""
    out: list[str] = []
    for raw in _FRONT_MATTER.sub("", body, count=1).splitlines():
        if raw.strip().startswith("%%"):
            # A comment is a whole line, ``;`` included: split first and its tail reads as code.
            continue
        out.extend(text for statement in raw.split(";") if (text := statement.strip()))
    return out


def _read_statement(text: str, chart: _Flowchart) -> None:
    """Fold one label-free statement: its ids, its ``:::`` classes, and an edge per arrow."""
    groups: list[list[str]] = [[]]
    for node, cls, arrow in _TOKEN.findall(text):
        if arrow:
            groups.append([])
        elif node:
            groups[-1].append(node)
            chart.nodes.add(node)
            if cls:
                chart.classed.add(node)
    for left, right in itertools.pairwise(groups):
        chart.edges.update((a, b) for a in left for b in right if a not in _KEYWORDS)


def _flowcharts(doc: str) -> list[_Flowchart]:
    return [chart for body in fences(doc) if (chart := _read(body)) is not None]


def node_ids(doc: str) -> set[str]:
    """Every flowchart node id across the document's fences, keywords and subgraphs excluded.

    The concept set of a diagram: what it is *about*, independent of the labels and the
    layout. Usually the facet with the tightest defensible tolerance, because a fixture
    fixes the things that exist even when it leaves their names free.
    """
    return {node for chart in _flowcharts(doc) for node in chart.nodes}


def edges(doc: str) -> set[str]:
    """Every ``a->b`` pair across the document's fences, as ``"a->b"`` strings.

    The diagram's shape rather than its contents: two diagrams over the same nodes with
    different edges are telling different stories.
    """
    return {f"{a}->{b}" for chart in _flowcharts(doc) for a, b in chart.edges}


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
    return {node for chart in _flowcharts(doc) for node in chart.nodes - chart.classed}


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
