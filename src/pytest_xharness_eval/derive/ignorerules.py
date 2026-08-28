"""The gitignore-style pattern subset that declares what is not decision surface (ADR 0026).

A skill's directory holds files an agent is never expected to reach: example galleries,
lockfiles, the skill's own unit tests. The project names them in its pytest config, one
``xharness_skill_ignore`` line each, and this module is the whole of what a line means.

Two steps, and they are separate on purpose. :func:`patterns_for` answers *which* lines
apply to a given skill -- a bare line applies to every skill, ``<selector>: <pattern>``
only to the skills whose name matches the ``fnmatch`` selector, in the way pytest's own
``markers`` lines pair a name with its text. :class:`IgnoreRules` then compiles those
patterns once and answers the only question anyone asks of them: is this path ignored.

Nothing here knows what a skill, a run or a harness is. That is why it is not in
:mod:`~pytest_xharness_eval.derive.skillcov`: the coverage module reads a tree and a ledger, and
this one is string matching it delegates to.
"""

from __future__ import annotations

# Standard Library
import fnmatch
import re
from dataclasses import dataclass
from typing import Self


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


@dataclass(frozen=True, slots=True)
class IgnoreRules:
    """Compiled ignore patterns: the one object that answers whether a path is ignored.

    Compiled once per skill, at collection, and then asked of every catalogued file, so a
    pattern is turned into a regex once rather than once per file.
    """

    rules: tuple[re.Pattern[str], ...]

    @classmethod
    def for_skill(cls, skill: str, lines: list[str]) -> Self:
        """The ``xharness_skill_ignore`` lines that apply to ``skill``, compiled.

        A malformed line raises :class:`ValueError` here, which is why the plugin runs this
        at configure time: an ignore rule that never matched anything is a silent
        measurement error, so it fails the session instead (ADR 0026).
        """
        return cls.compiled(patterns_for(skill, lines))

    @classmethod
    def compiled(cls, patterns: list[str]) -> Self:
        """Blank lines and ``#`` comments are dropped; braces expand; the rest become regexes."""
        out: list[re.Pattern[str]] = []
        for raw in patterns:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            out.extend(_glob_to_regex(p) for p in _expand_braces(line))
        return cls(tuple(out))

    def matches(self, rel: str) -> bool:
        """True when any rule matches the path or one of its parent directories."""
        return any(r.search(rel) for r in self.rules)
