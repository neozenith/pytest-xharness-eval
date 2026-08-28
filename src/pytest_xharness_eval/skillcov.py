"""Skill file coverage: which of the skill's files a run loaded or ran, and when (ADR 0022, ADR 0023).

A skill is a tree of documents, scripts and assets that an agent loads
hierarchically: ``SKILL.md`` first, then the resources it points at, then the
scripts it tells the agent to run. ``catalog`` lists that tree before a sweep
starts; ``annotate`` walks a run's per-turn ledger afterwards and records, per
file, the turns that loaded it and the turns that ran it. The difference between
the catalogue and what was touched is the run's ``not_loaded`` and ``not_run``
sets: the decision paths the agent never took.

Files that are part of the directory but not of the skill's decision surface
(example galleries, lockfiles, the skill's own unit tests) are excluded by the project's
``xharness_skill_ignore`` ini key, whose patterns are
:mod:`~pytest_xharness_eval.ignorerules`' business (ADR 0026). Ignored files are counted
here, never silently dropped.

Detection is textual and deliberately simple: a tool call touches a file when the
call's arguments contain ``<skill>/<relative path>``. That form is what both
harnesses see, whether the skill is mounted through ``--add-dir`` (Claude) or
copied under ``$CODEX_HOME/skills`` (Codex). A ``Skill`` tool invocation of the
skill counts as loading ``SKILL.md``.

The vocabulary of the answer is typed here — :class:`SkillFile` is one catalogued file,
:class:`FileCoverage` is that file plus the turns that touched it, and
:class:`SkillCoverage` derives the missed sets and the summary from those rows in one
place (ADR 0035). Their field names are the ``skill_coverage`` keys of ``result.json``.
"""

from __future__ import annotations

# Standard Library
import hashlib
import json
import posixpath
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

# Our Libraries
from pytest_xharness_eval import harness
from pytest_xharness_eval.ignorerules import IgnoreRules

if TYPE_CHECKING:
    # Our Libraries
    from pytest_xharness_eval.runresult import RunResult

# Directories that are never part of a skill's own surface, whatever the ignore rules say.
EXCLUDED_DIRS = {"evals", "captured", "node_modules", "__pycache__", ".git", ".mmdc_cache", "tmp", ".venv"}
SCRIPT_SUFFIXES = {".py", ".ts", ".js", ".sh", ".bash", ".zsh", ".mjs", ".cjs"}
DOC_SUFFIXES = {".md", ".mdx", ".txt", ".rst"}

# Tools whose arguments are commands rather than paths; a script named in one may be *run*.
_RUNNERS = r"(?:bun|bunx|uv|uvx|python3?|node|bash|sh|zsh|deno|npx)(?:\s+\S+)*?\s+"
_TEST_NAMES = re.compile(r"^(test_.*\.py|.*_test\.py|conftest\.py|.*\.test\.[cm]?[jt]s)$")


# -- the coverage vocabulary -------------------------------------------------------


class FileKind(StrEnum):
    """What a catalogued file is, decided from its path alone (ADR 0022).

    A ``str`` subclass, so it serialises as the bare word the wire format carries.
    """

    DOC = "doc"
    SCRIPT = "script"
    #: The skill's own unit tests: catalogued, but never expected of an agent, so they are
    #: excluded from the ``not_run`` set.
    TEST = "test"
    ASSET = "asset"


class Access(StrEnum):
    """The two ways a turn can touch a skill file, and the row field each records into."""

    LOADED = "loaded"
    RUN = "run"


@dataclass(frozen=True, slots=True, kw_only=True)
class SkillFile:
    """One file of the skill's tree, catalogued before a sweep starts (ADR 0022).

    Taken once, at collection, so every cell of a sweep is measured against the same
    inventory; ``sha256`` is what makes that claim checkable after the fact.
    """

    path: str
    kind: FileKind
    bytes: int
    sha256: str
    ignored: bool = False


@dataclass(slots=True)
class FileCoverage:
    """A catalogued file and the turns that loaded or ran it.

    The extra two fields are the whole difference between the catalogue and the answer,
    which is why this widens :class:`SkillFile` rather than nesting it: the wire format
    is one flat row per file.
    """

    path: str
    kind: FileKind
    bytes: int
    sha256: str
    ignored: bool
    loaded: list[int] = field(default_factory=list)
    run: list[int] = field(default_factory=list)

    @classmethod
    def of(cls, catalogued: SkillFile) -> Self:
        """An untouched row for a catalogued file."""
        return cls(
            path=catalogued.path,
            kind=catalogued.kind,
            bytes=catalogued.bytes,
            sha256=catalogued.sha256,
            ignored=catalogued.ignored,
        )

    @property
    def touched(self) -> bool:
        """True when any turn loaded or ran this file."""
        return bool(self.loaded or self.run)

    def touch(self, access: Access, turn: int) -> None:
        """Record that ``turn`` loaded or ran this file; a turn counts once per access."""
        turns = self.run if access is Access.RUN else self.loaded
        if turn not in turns:
            turns.append(turn)


@dataclass(frozen=True, slots=True, kw_only=True)
class CoverageSummary:
    """The counts and denominators the metrics record and the report row read.

    Ignored files are counted in ``ignored`` and in nothing else: they are not decision
    surface, so they must not move a coverage percentage (ADR 0026).
    """

    files: int
    ignored: int
    docs: int
    scripts: int
    tests: int
    assets: int
    loaded: int
    run: int

    @classmethod
    def over(cls, rows: list[FileCoverage]) -> Self:
        """Count ``rows``, splitting the ignored ones out of every figure but their own."""
        live = [r for r in rows if not r.ignored]
        return cls(
            files=len(live),
            ignored=len(rows) - len(live),
            docs=sum(r.kind is FileKind.DOC for r in live),
            scripts=sum(r.kind is FileKind.SCRIPT for r in live),
            tests=sum(r.kind is FileKind.TEST for r in live),
            assets=sum(r.kind is FileKind.ASSET for r in live),
            loaded=sum(r.touched for r in live),
            run=sum(bool(r.run) for r in live),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class SkillCoverage:
    """Which of a skill's files a run loaded or ran, and which it never touched (ADR 0022).

    The four path sets and the summary are all derived from the annotated rows by
    :meth:`over`, so they cannot disagree with each other or with ``files``.
    """

    skill: str
    files: list[FileCoverage]
    loaded: list[str]
    run: list[str]
    not_loaded: list[str]
    not_run: list[str]
    summary: CoverageSummary

    @classmethod
    def over(cls, skill: str, rows: list[FileCoverage]) -> Self:
        """Derive the sets and the summary from rows a run has already been annotated onto.

        Ignored files stay in ``files`` -- a run may well touch them, and hiding that would
        make the rules unauditable -- but count toward neither the missed sets nor the
        summary's denominators.
        """
        live = [r for r in rows if not r.ignored]
        scripts = [r.path for r in live if r.kind is FileKind.SCRIPT]
        run = [r.path for r in live if r.run]
        return cls(
            skill=skill,
            files=rows,
            loaded=[r.path for r in live if r.touched],
            run=run,
            not_loaded=[r.path for r in live if not r.touched],
            not_run=[p for p in scripts if p not in run],
            summary=CoverageSummary.over(rows),
        )


# -- catalogue -------------------------------------------------------------------


def kind_of(rel: str) -> FileKind:
    """The :class:`FileKind` of a relative path, from the path alone."""
    path = Path(rel)
    if _TEST_NAMES.match(path.name):
        return FileKind.TEST
    if path.suffix in SCRIPT_SUFFIXES or path.name == "Makefile":
        return FileKind.SCRIPT
    if path.suffix in DOC_SUFFIXES:
        return FileKind.DOC
    return FileKind.ASSET


def catalog(skill_dir: Path, ignore: list[str] | None = None) -> list[SkillFile]:
    """Every file of the skill, relative to its root, with kind, size, hash and ignored flag.

    ``ignore`` is the project's ``xharness_skill_ignore`` line list; the lines that
    apply to this skill are selected by its directory name.
    Ignored files stay in the list with ``ignored=True`` so a reader can see what
    the rules removed.
    """
    rules = IgnoreRules.for_skill(skill_dir.name, list(ignore or []))
    out: list[SkillFile] = []
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(skill_dir).parts
        if any(part in EXCLUDED_DIRS for part in rel_parts[:-1]) or path.name.startswith("."):
            continue
        rel = "/".join(rel_parts)
        data = path.read_bytes()
        out.append(
            SkillFile(
                path=rel,
                kind=kind_of(rel),
                bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                ignored=rules.matches(rel),
            )
        )
    return out


# -- annotation ------------------------------------------------------------------


def _call_text(name: str, arguments: Any) -> str:
    return arguments if isinstance(arguments, str) else json.dumps(arguments, ensure_ascii=False)


# -- effective working directory (ADR 0027) ---------------------------------------
#
# Claude Code's ``Bash`` tool is one persistent shell: a ``cd`` in one call is the
# working directory of the next, until the harness resets it (the reset is reported
# inside the tool result as ``Shell cwd was reset to <dir>``). An agent that does
# ``cd <skill> && cat SKILL.md`` and later ``bun run scripts/gate.ts`` never writes
# ``<skill>/scripts/gate.ts``, so the textual rule alone misses it. The shell is
# modelled per result: relative, file-looking tokens of a command are rewritten to
# ``<skill>/<sub>/<token>`` whenever the segment they sit in runs under the skill
# directory, and the rewritten text is matched by the same rule as before.

_SEGMENTS = re.compile(r"\s*(?:&&|\|\||;|\||\n)\s*")
_CD = re.compile(r"^\s*cd(?:\s+(\S+))?\s*$")
_CWD_RESET = re.compile(r"Shell cwd was reset to (\S+)")


def _chdir(cwd: str | None, target: str | None) -> str | None:
    """The directory after ``cd target`` from ``cwd``; None when it cannot be known."""
    if target is None:
        return None  # bare ``cd`` goes home: outside any skill
    target = target.strip("'\"")
    if target.startswith(("~", "$")):
        return None
    if target.startswith("/"):
        return posixpath.normpath(target)
    if cwd is None:
        return None
    return posixpath.normpath(posixpath.join(cwd, target))


def skill_subdir(cwd: str | None, skill: str) -> str | None:
    """``""`` when ``cwd`` is the skill's root, ``scripts`` when under it; None when outside."""
    if not cwd:
        return None
    parts = cwd.strip("/").split("/")
    if skill not in parts:
        return None
    root = len(parts) - 1 - parts[::-1].index(skill)
    return "/".join(parts[root + 1 :])


def _prefix_token(token: str, prefix: str, skill: str) -> str:
    """``scripts/gate.ts`` -> ``<skill>/scripts/gate.ts``.

    Flags, variables, redirections, absolute paths and already-qualified paths are
    left alone; so is a bare word with no ``.`` or ``/`` in it, which is a command,
    not a file.
    """
    quote = token[0] if token and token[0] in "'\"" else ""
    body = token[len(quote) :]
    if body.startswith("./"):
        body = body[2:]
    if not body or body[0] in "/-$<>" or f"{skill}/" in body or not re.search(r"[./]", body):
        return token
    return f"{quote}{prefix}{body}"


def resolve_command(command: str, skill: str, cwd: str | None) -> tuple[str, str | None]:
    """Rewrite a shell command's skill-relative paths as ``<skill>/...``; returns (text, cwd after).

    The command is split at ``&&``, ``||``, ``;``, ``|`` and newlines; a segment
    that is a ``cd`` moves the working directory for the segments after it.
    """
    out: list[str] = []
    for segment in _SEGMENTS.split(command):
        m = _CD.match(segment)
        if m:
            cwd = _chdir(cwd, m.group(1))
            out.append(segment)
            continue
        sub = skill_subdir(cwd, skill)
        if sub is None:
            out.append(segment)
            continue
        prefix = f"{skill}/{sub}/" if sub else f"{skill}/"
        out.append(" ".join(_prefix_token(tok, prefix, skill) for tok in segment.split(" ")))
    return "\n".join(out), cwd


def _command_of(arguments: Any) -> tuple[str, str | None]:
    """The shell command and the per-call working directory (Codex ``workdir``) of a tool input."""
    if isinstance(arguments, dict):
        command = arguments.get("command") or arguments.get("cmd") or ""
        if isinstance(command, list):
            command = " ".join(str(c) for c in command)
        workdir = arguments.get("workdir") or arguments.get("cwd")
        return str(command), str(workdir) if workdir else None
    return str(arguments or ""), None


def _access(tool: str, text: str, skill: str, entry: FileCoverage, shell_tools: frozenset[str]) -> Access | None:
    """How one tool call touched one catalogued file, or None if it did not."""
    needle = f"{skill}/{entry.path}"
    if tool == "Skill" and entry.path == "SKILL.md" and skill in text:
        return Access.LOADED
    if needle not in text:
        return None
    if entry.kind is FileKind.SCRIPT and tool in shell_tools:
        pattern = _RUNNERS + r"\S*" + re.escape(needle)
        if re.search(pattern, text) or re.search(r"(?:^|[\s;&|(])\./?\S*" + re.escape(needle) + r"(?:\s|$)", text):
            return Access.RUN
    return Access.LOADED


def annotate(skill: str, files: list[SkillFile], result: RunResult) -> SkillCoverage:
    """Walk a run's ledger and record, per catalogued file, the turns that loaded or ran it.

    Ignored files are still annotated (a run may well touch them); what that means for the
    missed sets and the summary is :meth:`SkillCoverage.over`'s to decide, not this walk's.
    """
    # Which tool names mean "ran a shell command", and which of those keep their cwd, is a
    # property of the harness that produced this run -- not a union of every provider's names
    # (ADR 0027, ADR 0034).
    agent = harness.get(result.harness)
    rows = [FileCoverage.of(f) for f in files]
    # The persistent shell's working directory, per result: it starts in the workspace
    # and follows every ``cd`` of a persistent shell tool until the harness resets it.
    cwd: str | None = str(result.workspace) if result.workspace else None
    for call in result.calls:
        for tool in call.tools:
            text = _call_text(tool.name, tool.input)
            if tool.name in agent.shell_tools:
                command, workdir = _command_of(tool.input)
                start = cwd if tool.name in agent.persistent_shells else (workdir or (str(result.workspace) or None))
                resolved, after = resolve_command(command, skill, start)
                if tool.name in agent.persistent_shells:
                    cwd = after
                text = f"{text}\n{resolved}"
            for row in rows:
                access = _access(tool.name, text, skill, row, agent.shell_tools)
                if access is not None:
                    row.touch(access, call.n)
        for res in call.results_in:
            m = _CWD_RESET.search(res.content or "")
            if m:
                cwd = m.group(1)
    return SkillCoverage.over(skill, rows)
