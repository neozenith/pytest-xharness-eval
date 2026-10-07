"""``verify.facets``: the markdown and mermaid facet extractors (ADR 0046)."""

from __future__ import annotations

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.verify import (
    facets,
)
from tests.support import DOC


def test_fences_split_by_whether_they_are_collapsed() -> None:
    assert facets.fence_count(DOC) == 2
    assert len(facets.visible_fences(DOC)) == 1
    assert len(facets.collapsed_fences(DOC)) == 1


def test_node_ids_and_edges_ignore_mermaid_keywords() -> None:
    assert facets.node_ids(DOC) == {"Loader", "Transform", "Report", "Reader", "Parser"}
    assert facets.edges(DOC) == {"Loader->Transform", "Transform->Report", "Reader->Parser"}
    assert "classDef" not in facets.node_ids(DOC)


def test_the_palette_facets_read_classdefs_not_substrings() -> None:
    assert facets.classdef_names(DOC) == {"io", "core"}
    assert facets.classdef_count(DOC) == 2
    assert facets.fill_colours(DOC) == {"#1f4e5f", "#7a4e2d"}
    assert facets.text_colours(DOC) == {"#ffffff"}


def test_unstyled_nodes_is_the_mandates_actual_claim() -> None:
    """ "A classDef exists" is satisfiable by styling one node of five; this is not."""
    assert facets.unstyled_nodes(DOC) == {"Transform"}
    inline = DOC.replace("    Transform --> Report[Report]", "    Transform:::io --> Report[Report]")
    assert facets.unstyled_nodes(inline) == set()


def test_headings_and_prose_facets() -> None:
    assert facets.headings(DOC) == {"Architecture", "Overview"}
    assert facets.headings_at(2)(DOC) == {"Overview"}
    assert "flowchart" not in facets.body_text(DOC)
    assert facets.hex_colours(DOC) == {"#1f4e5f", "#7a4e2d", "#ffffff"}


def _flow(*lines: str) -> str:
    return "```mermaid\nflowchart LR\n" + "\n".join(lines) + "\n```\n"


@pytest.mark.parametrize(
    "shape",
    [
        "[L]",
        "(L)",
        "([L])",
        "[(L)]",
        "[/L/]",
        "[/L\\]",
        "",
        "[[L]]",
        "((L))",
        "(((L)))",
        "{{L}}",
        "{L}",
        ">L]",
        '["a [b] (c)"]',
    ],
)
def test_every_node_shape_carries_its_inline_class(shape: str) -> None:
    """Issue #3, cause 1: five of twelve shapes defeated the single-pair matcher."""
    doc = _flow(f"A{shape}:::cls --> B:::cls")
    assert (facets.node_ids(doc), facets.unstyled_nodes(doc)) == ({"A", "B"}, set())


def test_edge_labels_and_chained_classes_are_not_nodes() -> None:
    """Issue #3, cause 2: ``-. telemetry .->`` and ``:::edge -->`` read as ids."""
    doc = _flow(
        "API[Gateway]:::ops -. telemetry .-> OPS[Observability]:::ops",
        "DNS[Route 53]:::edge --> CDN[CloudFront]:::edge -- forwards to --> WAF:::edge",
        "WAF == blocks ==> API",
        "API -->|calls| DB[(Store)]:::data",
    )
    assert facets.node_ids(doc) == {"API", "OPS", "DNS", "CDN", "WAF", "DB"}
    assert facets.edges(doc) == {"API->OPS", "DNS->CDN", "CDN->WAF", "WAF->API", "API->DB"}
    assert facets.unstyled_nodes(doc) == set()


def test_a_subgraph_is_a_container_and_a_comment_is_not_read() -> None:
    """Issue #3, cause 3, and a ``%%`` comment whose words looked like declarations."""
    doc = _flow(
        "%% Legend[a note] and Fake(node) live here; Secondary = hand-off to another view",
        "subgraph Group[A group]",
        "  KAFKA[[Kafka]]:::data",
        "  DEC{Decide}:::logic",
        "end",
        "KAFKA & DEC --> SINK(Sink); class SINK data",
    )
    assert facets.node_ids(doc) == {"KAFKA", "DEC", "SINK"}
    assert facets.edges(doc) == {"KAFKA->SINK", "DEC->SINK"}
    assert facets.unstyled_nodes(doc) == set()


def test_an_unclassed_node_is_still_reported() -> None:
    assert facets.unstyled_nodes(_flow("A[One]:::cls --> B[Two]", "B --> C((Three))")) == {"B", "C"}


def test_a_fence_holding_another_kind_of_diagram_declares_no_nodes() -> None:
    doc = "```mermaid\nsequenceDiagram\n  Alice->>Bob: Hello [there]\n```\n"
    assert (facets.node_ids(doc), facets.edges(doc), facets.unstyled_nodes(doc)) == (set(), set(), set())


def test_front_matter_keys_are_not_nodes() -> None:
    doc = "```mermaid\n---\nconfig:\n  flowchart:\n    wrappingWidth: 300\n---\nflowchart TB\n  A:::c --> B:::c\n```\n"
    assert facets.node_ids(doc) == {"A", "B"}
