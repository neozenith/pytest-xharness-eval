"""``verify.facets``: the markdown and mermaid facet extractors (ADR 0046)."""

from __future__ import annotations

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
