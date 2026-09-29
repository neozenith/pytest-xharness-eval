"""``derive.skillcov``: which skill files a run loaded or ran (ADR 0022, ADR 0027, ADR 0048)."""

# Standard Library
import dataclasses
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import (
    Call,
    ExecutedCommand,
    ToolCall,
    ToolResult,
    Usage,
)
from pytest_xharness_eval.derive import skillcov
from tests.support import _result, _skill


def test_a_coverage_row_widens_the_catalogued_file_by_exactly_the_two_access_lists() -> None:
    """``FileCoverage`` is a ``SkillFile`` plus the turns that touched it (ADR 0035).

    The same silent-drift hole this closes for ``RunResult`` and ``Subagent`` above: the
    wire format is one flat row per file, so the row *widens* the catalogued record
    rather than nesting it, and a field added to ``SkillFile`` alone would disappear from
    every annotated row and from ``result.json``'s ``skill_coverage.files`` with nothing
    failing. ``FileCoverage.of`` spreads the record, which turns the omission into a
    ``TypeError``; this pins the other half — that the row adds the two access lists and
    nothing else, so ``touch`` has a list for every :class:`Access` member.
    """
    catalogued = {f.name for f in dataclasses.fields(skillcov.SkillFile)}
    row = {f.name for f in dataclasses.fields(skillcov.FileCoverage)}
    assert catalogued <= row
    assert row - catalogued == {a.value for a in skillcov.Access} == {"loaded", "run"}


def test_catalog_applies_bare_and_skill_scoped_ignore_lines(tmp_path: Path) -> None:
    skill = _skill(tmp_path)  # its directory name is "demo"
    lines = [
        "# tests are not decision surface",
        "scripts/*.test.ts",
        "demo: assets/",
        "de*: scripts/package.json",
        "other-skill: SKILL.md",
        "",
    ]
    files = skillcov.catalog(skill, ignore=lines)
    ignored = {f.path for f in files if f.ignored}
    assert ignored == {"assets/icon.png", "scripts/check.test.ts", "scripts/package.json"}
    r = _result("m", Usage())
    cov = skillcov.annotate("demo", files, r)
    assert cov.summary.ignored == 3 and cov.summary.files == 5 and cov.summary.tests == 0
    assert "scripts/package.json" not in cov.not_loaded and "scripts/check.test.ts" not in cov.not_loaded


def test_a_skillignore_file_in_the_skill_is_not_read(tmp_path: Path) -> None:
    """ADR 0026: the ini key is the only source; a leftover dotfile is neither read nor catalogued."""
    skill = _skill(tmp_path)
    (skill / ".skillignore").write_text("assets/\n", encoding="utf-8")
    files = skillcov.catalog(skill)
    assert not any(f.ignored for f in files)
    assert ".skillignore" not in {f.path for f in files}


def test_catalog_lists_the_skill_surface_with_kinds_and_hashes(tmp_path: Path) -> None:
    files = skillcov.catalog(_skill(tmp_path))
    assert all(f.ignored is False for f in files)
    assert [(f.path, f.kind) for f in files] == [
        ("SKILL.md", "doc"),
        ("assets/icon.png", "asset"),
        ("resources/guide.md", "doc"),
        ("resources/unused.md", "doc"),
        ("scripts/check.test.ts", "test"),
        ("scripts/check.ts", "script"),
        ("scripts/never.py", "script"),
        ("scripts/package.json", "asset"),
    ]
    assert files[0].bytes == 6 and len(files[0].sha256) == 64


def test_annotate_marks_loaded_and_run_turns_and_derives_the_missed_sets(tmp_path: Path) -> None:
    files = skillcov.catalog(_skill(tmp_path))
    r = _result("m", Usage())
    r.calls = [
        Call(n=1, at="t", tools=[ToolCall("Skill", "demo", {"skill": "demo"})]),
        Call(n=2, at="t", tools=[ToolCall("Read", "", {"file_path": "/x/skills/demo/resources/guide.md"})]),
        Call(n=3, at="t", tools=[ToolCall("Bash", "", {"command": "cat /x/skills/demo/scripts/check.ts"})]),
        Call(
            n=4, at="t", tools=[ToolCall("Bash", "", {"command": "bun run /x/skills/demo/scripts/check.ts README.md"})]
        ),
        Call(
            n=5,
            at="t",
            tools=[
                ToolCall(
                    "exec",
                    "",
                    'await tools.exec_command({cmd: "sed -n 1,40p codex_home/skills/demo/resources/guide.md"})',
                )
            ],
        ),
        Call(n=6, at="t", tools=[ToolCall("Bash", "", {"command": "bun run /x/skills/demo/scripts/check.ts again"})]),
    ]
    cov = skillcov.annotate("demo", files, r)
    by = {f.path: f for f in cov.files}
    assert (by["SKILL.md"].loaded, by["SKILL.md"].run) == ([1], [])
    assert (by["resources/guide.md"].loaded, by["resources/guide.md"].run) == ([2, 5], [])
    # Turn 3 only read the script; turns 4 and 6 ran it (each turn counted once).
    assert (by["scripts/check.ts"].loaded, by["scripts/check.ts"].run) == ([3], [4, 6])
    assert cov.loaded == ["SKILL.md", "resources/guide.md", "scripts/check.ts"]
    assert cov.run == ["scripts/check.ts"]
    assert cov.not_loaded == [
        "assets/icon.png",
        "resources/unused.md",
        "scripts/check.test.ts",
        "scripts/never.py",
        "scripts/package.json",
    ]
    assert cov.not_run == ["scripts/never.py"]  # tests are never expected to run
    assert cov.summary == skillcov.CoverageSummary(
        files=8, ignored=0, docs=3, scripts=2, tests=1, assets=2, loaded=3, run=1
    )


@pytest.mark.parametrize(
    ("cwd", "target", "expected"),
    [
        ("/ws", "/x/skills/demo", "/x/skills/demo"),
        ("/x/skills/demo", "scripts", "/x/skills/demo/scripts"),
        ("/x/skills/demo/scripts", "..", "/x/skills/demo"),
        ("/x/skills/demo", "'/x/ws'", "/x/ws"),
        ("/x/skills/demo", None, None),  # bare ``cd`` goes home
        ("/x/skills/demo", "~/else", None),
        ("/x/skills/demo", "$DIR", None),
        (None, "scripts", None),  # relative from an unknown place stays unknown
    ],
)
def test_chdir_follows_absolute_relative_and_unknowable_targets(
    cwd: str | None, target: str | None, expected: str | None
) -> None:
    assert skillcov._chdir(cwd, target) == expected


def test_skill_subdir_locates_the_skill_root_inside_a_cwd() -> None:
    assert skillcov.skill_subdir("/x/skills/demo", "demo") == ""
    assert skillcov.skill_subdir("/x/skills/demo/scripts", "demo") == "scripts"
    assert skillcov.skill_subdir("/home/demo/ws", "demo") == "ws"  # last occurrence wins
    assert skillcov.skill_subdir("/x/ws", "demo") is None
    assert skillcov.skill_subdir(None, "demo") is None


def test_resolve_command_qualifies_relative_paths_after_a_cd_and_leaves_the_rest_alone() -> None:
    text, after = skillcov.resolve_command(
        'cd /x/skills/demo && cat SKILL.md && bun run scripts/check.ts "$F" --preset low 2>&1 | head -c 300',
        "demo",
        "/x/ws",
    )
    assert after == "/x/skills/demo"
    assert "demo/SKILL.md" in text
    assert 'bun run demo/scripts/check.ts "$F" --preset low 2>&1' in text
    # Runs of spaces (empty tokens) and a segment of only whitespace are not a crash.
    text, _ = skillcov.resolve_command("cat  SKILL.md   ;  \n\n", "demo", "/x/skills/demo")
    assert "demo/SKILL.md" in text
    # Outside the skill nothing is rewritten, and a bare word is never a path.
    text, after = skillcov.resolve_command("cd /x/ws; cat README.md; echo done", "demo", "/x/skills/demo")
    assert after == "/x/ws"
    assert "demo/README.md" not in text
    # Already-qualified, absolute, quoted and ./-prefixed forms resolve the same way.
    text, _ = skillcov.resolve_command(
        "./scripts/check.ts; cat '/abs/README.md'; ls demo/scripts/x.ts", "demo", "/x/skills/demo"
    )
    assert "demo/scripts/check.ts" in text
    assert "demo//abs" not in text
    assert "demo/demo/" not in text


@pytest.mark.parametrize(
    ("label", "command", "found"),
    [
        ("literal path", "bun run /x/skills/demo/scripts/check.ts doc.md", True),
        ("shell variable", "S=/x/skills/demo; bun run $S/scripts/check.ts doc.md", True),
        ("braced variable", "S=/x/skills/demo\nbun run ${S}/scripts/check.ts doc.md", True),
        ("exported variable", "export S=/x/skills/demo; bun run $S/scripts/check.ts doc.md", True),
        ("quoted value", 'S="/x/skills/demo"; bun run $S/scripts/check.ts doc.md', True),
        ("relative value", "S=../skills/demo/scripts; bun run $S/check.ts doc.md", True),
        ("a variable built from a variable", "B=/x/skills; S=$B/demo; bun run $S/scripts/check.ts", True),
        ("cd through a variable", "S=/x/skills/demo; cd $S && bun run scripts/check.ts", True),
        ("a prefix assignment scoped to its command", "S=/x/skills/demo bun run $S/scripts/check.ts", True),
        ("an unknown name stays unexpanded", "bun run $NOPE/scripts/check.ts", False),
    ],
)
def test_resolve_command_substitutes_the_variables_the_command_itself_assigned(
    label: str, command: str, found: bool
) -> None:
    """An agent that holds the skill directory in ``$S`` never writes the needle down (ADR 0048)."""
    resolved, _after = skillcov.resolve_command(command, "demo", "/x/ws")
    assert ("demo/scripts/check.ts" in f"{command}\n{resolved}") is found, label


def test_resolve_commands_variable_table_lives_and_dies_with_one_command() -> None:
    """Claude Code's Bash keeps its working directory between calls, but not its environment."""
    _first, after = skillcov.resolve_command("S=/x/skills/demo; echo $S", "demo", "/x/ws")
    later, _ = skillcov.resolve_command("bun run $S/scripts/check.ts", "demo", after)
    assert "demo/scripts/check.ts" not in later


def test_annotate_reads_the_command_the_harness_reports_as_executed(tmp_path: Path) -> None:
    """Codex's code-mode ``exec`` holds the skill path in a JS constant; the shell logs it expanded.

    The tool input is JavaScript, so the needle is nowhere in it. ``CommandExecution``
    carries the string the shell actually ran, which needs no parsing of the wrapper
    language it came from (ADR 0048).
    """
    files = skillcov.catalog(_skill(tmp_path))
    r = _result("m", Usage(), harness="codex")
    r.workspace = "/x/ws"
    r.calls = [
        Call(
            n=1,
            at="t",
            tools=[
                ToolCall(
                    "exec_command",
                    "",
                    {
                        "cmd": 'const base = "/x/skills/demo";\n'
                        "await tools.exec({cmd: `bun run ${base}/scripts/check.ts`})"
                    },
                )
            ],
            executed=[
                ExecutedCommand(tool="CommandExecution", command="bun run /x/skills/demo/scripts/check.ts", cwd="/x/ws")
            ],
        ),
        # A reported command is resolved at its own cwd, so a relative one still lands.
        Call(
            n=2,
            at="t",
            executed=[ExecutedCommand(tool="CommandExecution", command="cat resources/guide.md", cwd="/x/skills/demo")],
        ),
    ]
    cov = skillcov.annotate("demo", files, r)
    by = {f.path: f for f in cov.files}
    assert (by["scripts/check.ts"].loaded, by["scripts/check.ts"].run) == ([], [1])
    assert by["resources/guide.md"].loaded == [2]
    assert cov.run == ["scripts/check.ts"]


def test_annotate_counts_a_script_run_through_a_shell_variable(tmp_path: Path) -> None:
    """Claude's Bash input is the only record of what ran, so the variable is expanded here."""
    files = skillcov.catalog(_skill(tmp_path))
    r = _result("m", Usage(), harness="claude")
    r.workspace = "/x/ws"
    r.calls = [
        Call(
            n=1,
            at="t",
            tools=[
                ToolCall("Bash", "", {"command": "S=/x/skills/demo; cat $S/resources/guide.md"}),
                ToolCall("Bash", "", {"command": "S=/x/skills/demo/scripts; bun run $S/check.ts /x/ws/doc.md"}),
            ],
        )
    ]
    cov = skillcov.annotate("demo", files, r)
    by = {f.path: f for f in cov.files}
    assert by["resources/guide.md"].loaded == [1]
    assert by["scripts/check.ts"].run == [1]


def test_annotate_follows_the_claude_shells_cwd_and_the_harness_reset(tmp_path: Path) -> None:
    """Claude's Bash is one persistent shell, so a ``cd`` sticks until the harness resets it."""
    files = skillcov.catalog(_skill(tmp_path))
    r = _result("m", Usage(), harness="claude")
    r.workspace = "/x/ws"
    r.calls = [
        # Turn 1: cd into the skill and read SKILL.md by its bare name (the Opus pattern).
        Call(n=1, at="t", tools=[ToolCall("Bash", "", {"command": "cd /x/skills/demo && cat SKILL.md"})]),
        # Turn 2: the shell is still in the skill; a relative run of the gate counts as run.
        Call(n=2, at="t", tools=[ToolCall("Bash", "", {"command": "bun run scripts/check.ts /x/ws/doc.md"})]),
        # Turn 3: a relative cd deeper, then the script by bare name, still run.
        Call(
            n=3,
            at="t",
            tools=[
                ToolCall("Bash", "", {"command": "cd scripts; bun run check.ts /x/ws/doc.md; echo exit=$?"}),
            ],
            results_in=[ToolResult("toolu_3", 40, "clean\nShell cwd was reset to /x/ws")],
        ),
        # Turn 4: the harness reset the shell to the workspace, so the same text no longer touches the skill.
        Call(n=4, at="t", tools=[ToolCall("Bash", "", {"command": "bun run check.ts /x/ws/doc.md; cat SKILL.md"})]),
    ]
    cov = skillcov.annotate("demo", files, r)
    by = {f.path: f for f in cov.files}
    assert (by["SKILL.md"].loaded, by["SKILL.md"].run) == ([1], [])
    assert (by["scripts/check.ts"].loaded, by["scripts/check.ts"].run) == ([], [2, 3])
    assert cov.run == ["scripts/check.ts"]


def test_annotate_resolves_each_codex_exec_at_its_own_workdir(tmp_path: Path) -> None:
    """Codex runs every exec in a fresh process, so a ``cd`` in one never reaches the next.

    The tool vocabulary is the harness's own (ADR 0034): ``exec`` is a shell for Codex and
    nothing at all for Claude, so this case cannot be expressed on the same run as the one
    above -- a result comes from exactly one harness.
    """
    files = skillcov.catalog(_skill(tmp_path))
    r = _result("m", Usage(), harness="codex")
    r.workspace = "/x/ws"
    r.calls = [
        # Turn 1: the exec's own workdir is the skill, so a relative path resolves inside it.
        Call(
            n=1,
            at="t",
            tools=[
                ToolCall(
                    "exec",
                    "",
                    {"command": ["bash", "-lc", "cat resources/guide.md"], "workdir": "/x/skills/demo"},
                )
            ],
        ),
        # Turn 2 cds, but turn 3 starts again at its own workdir, so turn 3 never reaches the skill.
        Call(n=2, at="t", tools=[ToolCall("exec", "", {"command": "cd /x/skills/demo", "workdir": "/x/ws"})]),
        Call(n=3, at="t", tools=[ToolCall("exec", "", {"command": "cat resources/unused.md", "workdir": "/x/ws"})]),
    ]
    cov = skillcov.annotate("demo", files, r)
    by = {f.path: f for f in cov.files}
    assert by["resources/guide.md"].loaded == [1]
    assert by["resources/unused.md"].loaded == []
    assert cov.run == []
