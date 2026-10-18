"""Running the tool under test against what the agent left behind (ADR 0045).

A scenario case exercises a command-line tool (a linter, a prose gate, a formatter), and
the verdict is that tool's own answer on the agent's file. Every suite that did this wrote
the same thirty lines of :mod:`subprocess` around it, and every copy had to make the same
two decisions correctly:

* **A tool that could not run is an error, not a fail.** No interpreter on ``PATH``, a
  usage error, a crash with no report: none of those is a fact about the agent, so they
  raise :class:`RuntimeError` and the cell grades ``error``. Lint-style CLIs exit 1 both
  for "findings" and for some crashes, so exit 1 alone proves nothing; a report that
  parses is what distinguishes the two.
* **A broken fixture is an error, not a fail.** :func:`require_seed_fails` gates the
  seed first: a fixture that no longer reproduces its rule tests nothing, and a passing
  cell over it would be a lie.

This runs the *user's tool*, never an agent CLI. The rule against spawning a CLI from a
check (ADR 0002) is about the paid agent; a grader invoking the tool it grades with is
what a CI pipeline would do.

Scratch files a check needs go in :func:`scratch_dir`, *beside* the workspace and never
in it, so :func:`~pytest_xharness_eval.verify.checks.check_no_files_added` reads the same
whatever order a grader calls things in.
"""

from __future__ import annotations

# Standard Library
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterable, Mapping, Sequence

    # Our Libraries
    from pytest_xharness_eval.model.output import CaseOutput, Seed

#: How long one tool run may take before it counts as hung, in seconds.
TIMEOUT_S = 120
#: How many trailing lines of output a message quotes.
TAIL_LINES = 20

#: One argument of a tool's command line: a string, or a path (a workspace file, a script).
Arg = str | Path


@dataclass(frozen=True, slots=True)
class ToolRun:
    """One finished run of the tool under test: its command line, exit code and output."""

    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    def json(self) -> Any:
        """The tool's stdout parsed as JSON.

        Raises:
            RuntimeError: when stdout is not JSON. The tool did not produce a report, which
                is the host's failure, not the agent's.
        """
        try:
            return json.loads(self.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{self.command} printed no JSON (exit {self.returncode}):\n{self.tail()}") from exc

    @property
    def command(self) -> str:
        """The command line as one string, for a message."""
        return " ".join(self.argv)

    def tail(self, lines: int = TAIL_LINES) -> str:
        """The last ``lines`` lines of stdout and then stderr: what a reader needs to disagree."""
        out = "\n".join(self.stdout.rstrip().splitlines()[-lines:])
        err = "\n".join(self.stderr.rstrip().splitlines()[-lines:])
        return "\n".join(part for part in (out, err and f"[stderr]\n{err}") if part) or "(no output)"


def scratch_dir(output: CaseOutput | Seed) -> Path:
    """A directory for a check's own files, beside the workspace and never inside it.

    ``<workspace parent>/.<workspace name>.scratch``: inside the run's own directory, so
    it is inspectable and never the system temp dir, and outside the workspace, so a
    check that writes a fence to a file never shows up as a file the agent added.
    """
    scratch = output.workspace.parent / f".{output.workspace.name}.scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    return scratch


def _run(
    argv: Sequence[Arg], *, cwd: Path, ok_codes: Iterable[int], env: Mapping[str, str] | None, timeout_s: float
) -> ToolRun:
    """Run ``argv`` in ``cwd``; anything that means the tool did not run raises RuntimeError."""
    args = tuple(str(a) for a in argv)
    command = " ".join(args)
    try:
        done = subprocess.run(
            args,
            cwd=cwd,
            env={**os.environ, **env} if env is not None else None,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_s,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"the tool under test could not start ({command}): {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"the tool under test ran past {timeout_s}s and was killed: {command}") from exc
    run = ToolRun(argv=args, returncode=done.returncode, stdout=done.stdout, stderr=done.stderr)
    allowed = tuple(ok_codes)
    if run.returncode not in allowed:
        raise RuntimeError(f"{command} exited {run.returncode}, outside {list(allowed)}:\n{run.tail()}")
    return run


def run_tool(
    output: CaseOutput,
    argv: Sequence[Arg],
    *,
    cwd: Path | None = None,
    ok_codes: Iterable[int] = (0,),
    env: Mapping[str, str] | None = None,
    timeout_s: float = TIMEOUT_S,
) -> ToolRun:
    """Run the tool under test, by default in the workspace, and return what it did.

    ``argv`` may name workspace files relatively (the default ``cwd`` is the workspace) or
    through ``output.path(rel)``. ``env`` is merged over the current environment, so a
    tool still finds its interpreter on ``PATH``.

    Raises:
        RuntimeError: the tool could not start, ran past ``timeout_s``, or exited with a
            code outside ``ok_codes``. Each means the tool, not the agent, failed.
    """
    return _run(argv, cwd=cwd or output.workspace, ok_codes=ok_codes, env=env, timeout_s=timeout_s)


def _report_list(run: ToolRun, json_key: str | None) -> list[dict[str, Any]]:
    """The findings list in a parsed report; anything not shaped like one raises RuntimeError."""
    report = run.json()
    items = report.get(json_key) if json_key is not None and isinstance(report, dict) else report
    if not isinstance(items, list):
        where = f"key {json_key!r}" if json_key is not None else "top level"
        raise RuntimeError(f"{run.command} printed JSON with no findings list at its {where}:\n{run.tail()}")
    return [item if isinstance(item, dict) else {"message": str(item)} for item in items]


def findings(
    output: CaseOutput,
    argv: Sequence[Arg],
    *,
    json_key: str | None = "findings",
    ok_codes: Iterable[int] = (0, 1),
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout_s: float = TIMEOUT_S,
) -> list[dict[str, Any]]:
    """The findings a JSON-reporting tool prints for ``argv``.

    ``json_key`` names the list in the report object; ``None`` means the report *is* the
    list. Exit 1 is allowed by default because lint-style CLIs use it for "found something".

    Raises:
        RuntimeError: the tool did not run (see :func:`run_tool`), or printed no JSON, or
            JSON without the list. Exit 1 with no report is a crash, not a finding.
    """
    run = run_tool(output, argv, cwd=cwd, ok_codes=ok_codes, env=env, timeout_s=timeout_s)
    return _report_list(run, json_key)


def describe(finding: Mapping[str, Any]) -> str:
    """One finding as ``file:line rule message``, with ``?`` for a field the tool omits."""
    where = finding.get("file") or finding.get("path") or "?"
    return f"{where}:{finding.get('line', '?')} {finding.get('rule', '?')} {finding.get('message', '')}".rstrip()


def _listing(found: list[dict[str, Any]]) -> str:
    return "\n".join(f"  {describe(f)}" for f in found)


def check_tool_passes(
    output: CaseOutput,
    argv: Sequence[Arg],
    *,
    ok_codes: Iterable[int] = (0, 1),
    json_key: str | None = "findings",
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout_s: float = TIMEOUT_S,
) -> None:
    """The tool under test exits 0 on what the agent left.

    Any code in ``ok_codes`` other than 0 is the agent's failure, and the message lists
    the findings when the tool printed a JSON report, else the tail of its output. A code
    outside ``ok_codes`` raises :class:`RuntimeError` (the tool crashed).
    """
    run = run_tool(output, argv, cwd=cwd, ok_codes=ok_codes, env=env, timeout_s=timeout_s)
    if run.returncode == 0:
        return
    try:
        evidence = _listing(_report_list(run, json_key))
    except RuntimeError:
        # Not a report: the output itself is the evidence. The exit code already decided.
        evidence = run.tail()
    raise AssertionError(f"{run.command} exited {run.returncode} on the agent's work:\n{evidence}")


def check_tool_clean(
    output: CaseOutput,
    argv: Sequence[Arg],
    *,
    json_key: str | None = "findings",
    ok_codes: Iterable[int] = (0, 1),
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout_s: float = TIMEOUT_S,
) -> None:
    """The tool under test reports zero findings, of any rule, on what the agent left.

    Zero findings alone is rarely the whole verdict: deleting the offending text also
    reaches zero. Pair it with the :mod:`~pytest_xharness_eval.verify.content` checks.
    """
    found = findings(output, argv, json_key=json_key, ok_codes=ok_codes, cwd=cwd, env=env, timeout_s=timeout_s)
    assert not found, f"{len(found)} finding(s) remain after the run:\n{_listing(found)}"


def require_seed_fails(
    output: CaseOutput | Seed,
    seed: Path | str,
    argv: Sequence[Arg],
    *,
    rules: Iterable[str],
    name: str = "seed.md",
    exactly: bool = True,
    json_key: str | None = "findings",
    ok_codes: Iterable[int] = (0, 1),
    env: Mapping[str, str] | None = None,
    timeout_s: float = TIMEOUT_S,
) -> None:
    """The seed still fails the tool with ``rules``, so the case still tests them.

    ``seed`` is a path to the committed fixture file, or its text, which is written to
    ``name`` under :func:`scratch_dir`. ``argv`` is the command *prefix*: the seed's path
    is appended as the last argument, which is how lint and gate CLIs take a file.
    ``exactly`` demands the set of rules reported equals ``rules``; otherwise each of
    ``rules`` must be among them.

    Raises:
        RuntimeError: the seed does not reproduce ``rules``, or the tool did not run. A
            fixture that drifted from its rule is the host's fault, so the cell errors.
    """
    if isinstance(seed, Path):
        target = seed
    else:
        target = scratch_dir(output) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(seed, encoding="utf-8")
    run = _run([*argv, target], cwd=target.parent, ok_codes=ok_codes, env=env, timeout_s=timeout_s)
    found = _report_list(run, json_key)
    want = set(rules)
    got = {str(f.get("rule")) for f in found}
    holds = got == want if exactly else want <= got
    if not holds:
        claim = "alone" if exactly else "among others"
        raise RuntimeError(
            # Rules first, path last: a record keeps only the first line's opening characters.
            f"the seed should fail {sorted(want)} {claim}; it reports {sorted(got)} ({target.name}). "
            f"The fixture no longer tests what the case says. Gated at {target}:\n{_listing(found) or run.tail()}"
        )
