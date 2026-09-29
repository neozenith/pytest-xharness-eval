"""``derive.ignorerules``: selecting and matching skill-ignore lines (ADR 0026, ADR 0035)."""


# Standard Library

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.derive import ignorerules


@pytest.mark.parametrize(
    ("pattern", "matches", "misses"),
    [
        (
            "resources/examples/**",
            ["resources/examples/a.png", "resources/examples/sub/b.md"],
            ["resources/a.md", "examples/x"],
        ),
        ("scripts/{Makefile,CLAUDE.md}", ["scripts/Makefile", "scripts/CLAUDE.md"], ["scripts/README.md", "Makefile"]),
        ("scripts/*.json", ["scripts/package.json"], ["scripts/sub/x.json", "package.json"]),
        ("scripts/_*.py", ["scripts/_helper.py"], ["scripts/helper.py"]),
        ("scripts/*.test.ts", ["scripts/a.test.ts"], ["scripts/a.ts"]),
        ("scripts/bun*", ["scripts/bun.lock", "scripts/bunfig.toml"], ["scripts/sub/bun.lock"]),
        ("README.md", ["README.md", "resources/examples/README.md"], ["README.mdx", "docs/README"]),
        ("assets/", ["assets/icon.png", "assets/deep/x", "other/assets/x.png"], ["x/assetsy", "assetsx/y"]),
        ("# a comment", [], ["anything"]),
    ],
)
def test_skill_ignore_globs(pattern: str, matches: list[str], misses: list[str]) -> None:
    rules = ignorerules.IgnoreRules.compiled([pattern, ""])
    assert all(rules.matches(p) for p in matches), pattern
    assert not any(rules.matches(p) for p in misses), pattern


@pytest.mark.parametrize(
    ("line", "applies"),
    [
        ("README.md", True),
        ("mermaidjs-diagrams: README.md", True),
        ("mermaidjs-diagrams : README.md", True),
        ("*-diagrams: README.md", True),
        ("mermaidjs-diagrams: scripts/{Makefile,CLAUDE.md}", True),
        ("other: README.md", False),
        ("mermaid: README.md", False),  # an exact name, not a prefix
    ],
)
def test_patterns_for_selects_lines_by_skill_name(line: str, applies: bool) -> None:
    resolved = ignorerules.patterns_for("mermaidjs-diagrams", [line])
    assert resolved == ([line.partition(":")[2].strip() or line] if applies else [])


@pytest.mark.parametrize("line", ["mermaidjs-diagrams:", ": README.md", ":"])
def test_patterns_for_rejects_a_selector_without_a_pattern(line: str) -> None:
    with pytest.raises(ValueError, match="xharness_skill_ignore"):
        ignorerules.patterns_for("mermaidjs-diagrams", [line])
