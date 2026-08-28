"""Skill file coverage: which of the skill's files a run loaded or ran, and when (ADR 0022, ADR 0023).

A skill is a tree of documents, scripts and assets that an agent loads
hierarchically: ``SKILL.md`` first, then the resources it points at, then the
scripts it tells the agent to run. ``catalog`` lists that tree before a sweep
starts; ``annotate`` walks a run's per-turn ledger afterwards and records, per
file, the turns that loaded it and the turns that ran it. The difference between
the catalogue and what was touched is the run's ``not_loaded`` and ``not_run``
sets: the decision paths the agent never took.

Files that are part of the directory but not of the skill's decision surface
(example galleries, lockfiles, the skill's own unit tests) are excluded with
gitignore-style patterns from the project's ``xharness_skill_ignore`` ini key
(ADR 0026). Each line is either a bare pattern, which applies to every skill, or
``<skill>: <pattern>``, which applies to the skills whose name matches the
``fnmatch`` selector before the colon, in the way pytest's own ``markers`` lines
pair a name with its text. Ignored files are counted, never silently dropped.

Detection is textual and deliberately simple: a tool call touches a file when the
call's arguments contain ``<skill>/<relative path>``. That form is what both
harnesses see, whether the skill is mounted through ``--add-dir`` (Claude) or
copied under ``$CODEX_HOME/skills`` (Codex). A ``Skill`` tool invocation of the
skill counts as loading ``SKILL.md``.
"""

from __future__ import annotations

# Standard Library
import fnmatch
import hashlib
import json
import posixpath
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Our Libraries
from pytest_xharness_eval import harness

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


# -- ignore patterns (gitignore-style subset) -------------------------------------


def _expand_braces(pattern: str) -> list[str]:
    """``scripts/{Makefile,CLAUDE.md}`` -> two patterns; nested braces are not supported."""
    m = re.search(r"\{([^{}]*)\}", pattern)
    if not m:
        return [pattern]
    head, tail = pattern[: m.start()], pattern[m.end() :]
    out: list[str] = []
    for alt in m.group(1).split(","):
        out.extend(_expand_braces(head + alt + tail))
    return out


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """One gitignore-style pattern to a regex over ``/``-separated relative paths.

    ``**`` spans directories, ``*`` and ``?`` stay inside one path segment, a
    trailing ``/`` names a directory and everything under it, and a pattern with
    no ``/`` (other than a trailing one) matches at any depth.
    """
    directory = pattern.endswith("/")
    body = pattern.rstrip("/")
    anchored = "/" in body
    body = body.lstrip("/")
    out = ""
    i = 0
    while i < len(body):
        ch = body[i]
        if body.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif body.startswith("**", i):
            out += ".*"
            i += 2
        elif ch == "*":
            out += "[^/]*"
            i += 1
        elif ch == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(ch)
            i += 1
    prefix = "^" if anchored else "(?:^|.*/)"
    suffix = "(?:/.*)?$" if directory else "$"
    return re.compile(prefix + out + suffix)


def patterns_for(skill: str, lines: list[str]) -> list[str]:
    """The patterns of ``xharness_skill_ignore`` that apply to ``skill``.

    A line with no ``:`` applies to every skill. ``<selector>: <pattern>`` applies
    when ``fnmatch(skill, selector)`` holds, so ``mermaidjs-diagrams: README.md``
    names one skill and ``*-diagrams: README.md`` a family. Blank lines and ``#``
    comments are dropped here; a line whose pattern is empty is an error, since a
    selector with nothing after it ignores nothing and is almost certainly a typo.
    """
    out: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        selector, sep, pattern = line.partition(":")
        if not sep:
            out.append(line)
            continue
        selector, pattern = selector.strip(), pattern.strip()
        if not selector or not pattern:
            raise ValueError(f"xharness_skill_ignore: expected '<skill>: <pattern>' or '<pattern>', got {line!r}")
        if fnmatch.fnmatchcase(skill, selector):
            out.append(pattern)
    return out


def compile_ignore(patterns: list[str]) -> list[re.Pattern[str]]:
    """Blank lines and ``#`` comments are dropped; braces expand; the rest become regexes."""
    out: list[re.Pattern[str]] = []
    for raw in patterns:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.extend(_glob_to_regex(p) for p in _expand_braces(line))
    return out


def is_ignored(rel: str, rules: list[re.Pattern[str]]) -> bool:
    """True when any rule matches the path or one of its parent directories."""
    return any(r.search(rel) for r in rules)


# -- catalogue -------------------------------------------------------------------


def kind_of(rel: str) -> str:
    """``doc``, ``script``, ``test`` or ``asset`` from the path alone.

    Tests are the skill's own unit tests; an agent is not expected to run them, so
    they are catalogued but excluded from the ``not_run`` set.
    """
    path = Path(rel)
    if _TEST_NAMES.match(path.name):
        return "test"
    if path.suffix in SCRIPT_SUFFIXES or path.name == "Makefile":
        return "script"
    if path.suffix in DOC_SUFFIXES:
        return "doc"
    return "asset"


def catalog(skill_dir: Path, ignore: list[str] | None = None) -> list[dict[str, Any]]:
    """Every file of the skill, relative to its root, with kind, size, hash and ignored flag.

    ``ignore`` is the project's ``xharness_skill_ignore`` line list; the lines that
    apply to this skill (by its directory name) are resolved with ``patterns_for``.
    Ignored files stay in the list with ``ignored: True`` so a reader can see what
    the rules removed.
    """
    rules = compile_ignore(patterns_for(skill_dir.name, list(ignore or [])))
    out: list[dict[str, Any]] = []
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(skill_dir).parts
        if any(part in EXCLUDED_DIRS for part in rel_parts[:-1]) or path.name.startswith("."):
            continue
        rel = "/".join(rel_parts)
        data = path.read_bytes()
        out.append(
            {
                "path": rel,
                "kind": kind_of(rel),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "ignored": is_ignored(rel, rules),
            }
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


def _access(tool: str, text: str, skill: str, entry: dict[str, Any], shell_tools: frozenset[str]) -> str | None:
    """``run``, ``loaded`` or None for one tool call against one catalogued file."""
    needle = f"{skill}/{entry['path']}"
    if tool == "Skill" and entry["path"] == "SKILL.md" and skill in text:
        return "loaded"
    if needle not in text:
        return None
    if entry["kind"] == "script" and tool in shell_tools:
        pattern = _RUNNERS + r"\S*" + re.escape(needle)
        if re.search(pattern, text) or re.search(r"(?:^|[\s;&|(])\./?\S*" + re.escape(needle) + r"(?:\s|$)", text):
            return "run"
    return "loaded"


def annotate(skill: str, files: list[dict[str, Any]], result: RunResult) -> dict[str, Any]:
    """Per-file turns that loaded or ran it, plus the not-loaded / not-run sets.

    Ignored files are still annotated (a run may well touch them) but never count
    toward the missed sets or the summary's denominators.
    """
    # Which tool names mean "ran a shell command", and which of those keep their cwd, is a
    # property of the harness that produced this run -- not a union of every provider's names
    # (ADR 0027, ADR 0034).
    agent = harness.get(result.harness)
    rows = [{**f, "ignored": bool(f.get("ignored")), "loaded": [], "run": []} for f in files]
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
                if access and call.n not in row[access]:
                    row[access].append(call.n)
        for res in call.results_in:
            m = _CWD_RESET.search(res.content or "")
            if m:
                cwd = m.group(1)
    live = [r for r in rows if not r["ignored"]]
    scripts = [r["path"] for r in live if r["kind"] == "script"]
    loaded = [r["path"] for r in live if r["loaded"] or r["run"]]
    run = [r["path"] for r in live if r["run"]]
    return {
        "skill": skill,
        "files": rows,
        "loaded": loaded,
        "run": run,
        "not_loaded": [r["path"] for r in live if not (r["loaded"] or r["run"])],
        "not_run": [p for p in scripts if p not in run],
        "summary": {
            "files": len(live),
            "ignored": len(rows) - len(live),
            "docs": sum(r["kind"] == "doc" for r in live),
            "scripts": len(scripts),
            "tests": sum(r["kind"] == "test" for r in live),
            "assets": sum(r["kind"] == "asset" for r in live),
            "loaded": len(loaded),
            "run": len(run),
        },
    }
