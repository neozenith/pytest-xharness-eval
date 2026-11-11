"""The Kiro harness: how ``kiro-cli chat --v3`` is invoked, and how its session log folds.

Kiro's V3 engine writes ``$KIRO_HOME/sessions/<workspace>/sess_<uuid>/messages.jsonl``, where
``<workspace>`` is the first 16 hex digits of the SHA-256 of the workspace path, with
``session.json`` beside it naming the session and its model. A subagent's transcript is
``sub-executions/<subSessionId>.jsonl`` in the same directory, named by the parent's
``sub_agent_start`` record. There is no ``--session-id``, so the correlation contract is
isolation, as for Codex (ADR 0005): ``KIRO_HOME`` points at a private per-run directory, and
exactly one session can then exist under it. Authentication lives outside ``KIRO_HOME`` (the
desktop login's store, or ``KIRO_API_KEY``), so nothing needs seeding but the skill.

Kiro bills credits, not tokens (ADR 0078). Each prompt turn closes with a ``usage_summary``
whose ``promptTurnSummaries[].usage`` is the turn's credits, subagents' work included, and no
record carries a provider token count. So one :class:`Call` is folded per metered turn, its
usage is credits alone, and a subagent's ledger meters nothing of its own: its work is already
inside the turn that spawned it.

The log names neither its own session id nor a concrete model (``reasoningModelId`` is the
router's ``qdev::auto``). Both come from ``session.json`` at run time and from the stored
``result.json`` on replay: that pair is the side-channel :class:`KiroSessionLog` carries.

Verified against kiro-cli 3.1.0 from interactive V3 sessions and the CLI's own help and
bundle; no paid headless run has been made yet (ADR 0002).
"""

from __future__ import annotations

# Standard Library
import json
import os
import shutil
import time
from collections import Counter
from typing import TYPE_CHECKING, Any

# Our Libraries
from pytest_xharness_eval.harness import records as record_kinds
from pytest_xharness_eval.harness import threads
from pytest_xharness_eval.harness.base import (
    DEFAULT_TIMEOUT_S,
    TIMED_OUT,
    Evidence,
    Harness,
    RunError,
    SessionLog,
    UnfoldedRun,
    copy_skill,
    mark_timed_out,
    register,
    seconds_idle,
    spawn,
)
from pytest_xharness_eval.harness.normalise import (
    Numbered,
    ended,
    join_text,
    read_jsonl_numbered,
    summarise,
    text_of,
)
from pytest_xharness_eval.model import workspace as ws
from pytest_xharness_eval.model.runresult import Call, RunResult, Subagent, ToolCall, ToolResult, Usage

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.model.layout import SessionDir

#: Kiro's reasoning-effort ladder, lowest rung first: ``kiro-cli chat --effort``'s own values
#: (kiro-cli 3.1.0 help, and the agent's ``["low","medium","high","xhigh","max"]`` enum).
#: The order is the ladder, not a set: ``mid`` resolves by index (ADR 0049).
KIRO_EFFORTS = ("low", "medium", "high", "xhigh", "max")

#: The flags that make a run headless, unattended and on the V3 engine whose log this folds.
#: ``--trust-workspace`` skips the trust prompt for this launch without saving the decision.
_HEADLESS = ["--v3", "--no-interactive", "--trust-all-tools", "--trust-workspace", "--wrap", "never"]

#: The directory, inside a session, that holds its subagents' transcripts.
SUB_EXECUTIONS = "sub-executions"
#: The record ``promptTurnSummaries`` states credits in; any other unit stops the fold.
CREDIT_UNIT = "credit"
#: ``usage_summary.status`` to the stop reason its call records.
_STOP = {"success": "end_turn", "aborted": "aborted", "failed": "failed"}


# -- invocation ------------------------------------------------------------------------


def effort_argv(effort: str | None) -> list[str]:
    """``--effort <rung>``, or nothing when no rung was asked for (ADR 0049)."""
    return ["--effort", effort] if effort else []


def primary_session(home: Path) -> Path:
    """The one session directory under a private ``KIRO_HOME``; anything else is a hard failure.

    A private home holds only what this run wrote, so more than one session, or none, means
    the run cannot prove which log is its own (the evidence contract).
    """
    found = sorted(p.parent for p in home.glob("sessions/*/sess_*/messages.jsonl"))
    if len(found) != 1:
        names = ", ".join(p.name for p in found) or "none"
        raise RunError(f"expected exactly one session under private KIRO_HOME {home}, found {len(found)} ({names})")
    return found[0]


def session_meta(session: Path) -> tuple[str, str]:
    """The session id and model ``session.json`` names; a session that names no id is refused."""
    meta = json.loads((session / "session.json").read_text(encoding="utf-8"))
    session_id = str(meta.get("id") or "")
    if not session_id:
        raise RunError(f"{session / 'session.json'} names no session id")
    return session_id, str(meta.get("modelId") or "")


def run_kiro(
    prompt: str,
    model: str,
    workspace: Path,
    effort: str | None = None,
    skill_dir: Path | None = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> RunResult:  # pragma: no cover - spawns a real CLI (ADR 0002)
    """Run ``kiro-cli chat --v3 --no-interactive`` under a private KIRO_HOME; return the normalised RunResult."""
    run_dir = workspace.parent / f"{workspace.name}.kiro"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    private_home = run_dir / "kiro_home"
    private_home.mkdir(parents=True)
    if skill_dir is not None:
        copy_skill(skill_dir, private_home / "skills" / skill_dir.name)

    env = {**os.environ, "KIRO_HOME": str(private_home)}
    cmd = ["kiro-cli", "chat", *_HEADLESS, "--model", model, *effort_argv(effort), prompt]

    before = ws.snapshot(workspace)
    start = time.monotonic()
    proc = spawn(cmd, cwd=workspace, env=env, timeout_s=timeout_s)
    ended_at = time.time()
    wall_ms = int((time.monotonic() - start) * 1000)
    after = ws.snapshot(workspace)

    session = primary_session(private_home)
    session_id, logged_model = session_meta(session)
    log = session / "messages.jsonl"
    subs = sorted((session / SUB_EXECUTIONS).glob("*.jsonl"))
    files_written = ws.diff(before, after)
    timed_out = proc.returncode == TIMED_OUT
    idle = seconds_idle([log, *subs], ended_at) if timed_out else None
    try:
        result = KiroSessionLog(log, proc.returncode, session_id, logged_model or model, subs).to_result(
            workspace, files_written
        )
    except threads.SubagentMismatch as exc:
        # Billed but unfoldable: the private home goes with the run directory (ADR 0072).
        evidence = Evidence(
            harness="kiro",
            session_id=session_id,
            log=log,
            transcripts=tuple(subs),
            workspace=workspace,
            files_written=tuple(files_written),
            exit_code=proc.returncode,
            timed_out_after_s=timeout_s if timed_out else None,
            idle_before_timeout_s=idle,
        )
        raise UnfoldedRun(str(exc), evidence) from exc
    if not result.duration_ms:
        result.duration_ms = wall_ms
    if timed_out:
        mark_timed_out(result, timeout_s, idle)
    return result


# -- folding the log -------------------------------------------------------------------


def turn_credits(payload: dict[str, Any], where: str) -> float:
    """A ``usage_summary``'s credits, summed over its prompt turns; a unit other than credits stops the fold.

    Pricing in a unit the log did not state would be a guess (ADR 0078).
    """
    total = 0.0
    for summary in payload.get("promptTurnSummaries") or []:
        unit = summary.get("unit")
        if unit is not None and unit != CREDIT_UNIT:
            raise RunError(f"{where}: a usage_summary meters {unit!r}, not {CREDIT_UNIT!r}")
        total += float(summary.get("usage") or 0.0)
    return total


class _Ledger:
    """Fold one Kiro transcript into calls: one per ``usage_summary``, or one per transcript when none.

    A turn's records arrive in order -- ``turn_start``, the assistant's ``Reasoning`` and ``Say``
    chunks, its ``tool_call`` and ``tool_result`` records -- and the turn closes at its
    ``usage_summary``. A subagent's transcript has no ``usage_summary`` (its credits are the
    parent turn's), so :meth:`finish` closes whatever it holds as one unmetered call.
    """

    def __init__(self) -> None:
        self.calls: list[Call] = []
        self.tools: Counter[str] = Counter()
        self.requests = 0
        self.duration_ms = 0
        self._tool_calls: list[ToolCall] = []
        self._outputs: list[ToolResult] = []
        self._carried: list[ToolResult] = []
        self._names: dict[str, str] = {}
        self._text = ""
        self._thinking = ""
        self._lines: list[int] = []

    def record(self, line: int, rec: dict[str, Any], where: str) -> None:
        payload = rec.get("payload") or {}
        at = str(rec.get("timestamp") or "")
        self._lines.append(line)
        kind = payload.get("type")
        if kind == "assistant":
            content = text_of(payload.get("content"))
            if payload.get("operationType") == "Say":
                self._text = join_text(self._text, content)
            else:
                self._thinking = join_text(self._thinking, content)
        elif kind == "tool_call":
            self._tool_call(payload, at)
        elif kind == "tool_result":
            self._tool_result(payload, at)
        elif kind == "usage_summary":
            self.requests += len(payload.get("requestIds") or [])
            self.duration_ms += int(payload.get("elapsedTime") or 0)
            stop = _STOP.get(str(payload.get("status") or "success"), str(payload.get("status")))
            self._close(at, Usage(credits=turn_credits(payload, where)), stop)

    def _tool_call(self, payload: dict[str, Any], at: str) -> None:
        name = str(payload.get("toolName") or payload.get("actionType") or "unknown")
        tool_id = str(payload.get("toolCallId") or "")
        args = payload.get("args")
        self._names[tool_id] = name
        self.tools[name] += 1
        self._tool_calls.append(
            ToolCall(name=name, summary=summarise(name, args), input=args, id=tool_id, started_at=at)
        )

    def _tool_result(self, payload: dict[str, Any], at: str) -> None:
        tool_id = str(payload.get("toolCallId") or "")
        text = text_of(payload.get("content"))
        self._outputs.append(
            ToolResult(tool=self._names.get(tool_id, "unknown"), chars=len(text), content=text, id=tool_id)
        )
        if not ended(self._tool_calls, tool_id, at) and self.calls:
            ended(self.calls[-1].tools, tool_id, at)

    def _close(self, at: str, usage: Usage, stop_reason: str) -> None:
        self.calls.append(
            Call(
                n=len(self.calls) + 1,
                at=at,
                usage=usage,
                stop_reason=stop_reason,
                text=self._text,
                thinking=self._thinking,
                tools=self._tool_calls,
                results_in=self._carried + self._outputs,
                records=self._lines,
            )
        )
        self._carried, self._outputs = [], []
        self._tool_calls, self._text, self._thinking, self._lines = [], "", "", []

    def finish(self, at: str) -> None:
        """Close what is left: trailing records join the last call, or form the one unmetered call."""
        if self._tool_calls or self._text or self._thinking or not self.calls:
            if self._lines:
                self._close(at, Usage(), "end_turn")
            return
        self.calls[-1].records.extend(self._lines)
        self._lines = []


def fold(records: Numbered, where: str) -> _Ledger:
    """Fold one transcript's records into a ledger."""
    ledger = _Ledger()
    last = ""
    for line, rec in records:
        ledger.record(line, rec, where)
        last = str(rec.get("timestamp") or last)
    ledger.finish(last)
    return ledger


def spawns_in(thread: str, records: Numbered, calls: list[Call], where: str) -> list[threads.Spawn]:
    """Every ``sub_agent_start`` one transcript logged: the spawn names its transcript by ``subSessionId``."""
    spawns: list[threads.Spawn] = []
    for line, rec in records:
        payload = rec.get("payload") or {}
        if payload.get("type") == "sub_agent_start":
            key = str(payload.get("subSessionId") or "")
            turn = threads.turn_of_line(calls, line, where)
            spawns.append(threads.Spawn(thread=thread, turn=turn, id=key, key=key))
    return spawns


def _starts(records: Numbered) -> dict[str, dict[str, Any]]:
    """Each ``sub_agent_start`` payload a transcript logged, by the subagent it names."""
    out: dict[str, dict[str, Any]] = {}
    for _, rec in records:
        payload = rec.get("payload") or {}
        if payload.get("type") == "sub_agent_start":
            out[str(payload.get("subSessionId") or "")] = payload
    return out


def subagents_of(transcripts: list[Path], primary: Numbered, calls: list[Call], where: str) -> list[Subagent]:
    """Fold each ``sub-executions/<id>.jsonl`` into a subagent ledger, linked to its spawn (ADR 0072).

    A transcript's id is its file stem, the ``subSessionId`` the spawning transcript's
    ``sub_agent_start`` names. Its parent is whichever transcript logged that start: the
    primary, or another subagent for a nested spawn.
    """
    spawns = spawns_in(threads.PRIMARY, primary, calls, where)
    started = {key: (threads.PRIMARY, payload) for key, payload in _starts(primary).items()}
    folded: list[tuple[Path, Numbered, _Ledger]] = []
    for path in transcripts:
        records = read_jsonl_numbered(path)
        ledger = fold(records, path.name)
        spawns += spawns_in(path.stem, records, ledger.calls, path.name)
        started.update({key: (path.stem, payload) for key, payload in _starts(records).items()})
        folded.append((path, records, ledger))

    links = threads.link(
        spawns,
        (
            threads.Thread(id=p.stem, parent=started.get(p.stem, (threads.PRIMARY, {}))[0], keys=frozenset({p.stem}))
            for p, _, _ in folded
        ),
    )
    subs: list[Subagent] = []
    for path, records, ledger in folded:
        placed = links[path.stem]
        start = started[path.stem][1]
        started_at, ended_at = threads.span(records, path.name)
        subs.append(
            Subagent.folded(
                ledger.calls,
                agent=str(start.get("subAgentName") or "subagent"),
                id=path.stem,
                log=str(path),
                spawned_by=placed.spawn.id,
                parent=placed.spawn.thread,
                depth=placed.depth,
                parent_turn=placed.parent_turn,
                started_at=started_at,
                ended_at=ended_at,
                description=str(start.get("explanation") or ""),
            )
        )
    return subs


class KiroSessionLog(SessionLog):
    """A Kiro ``messages.jsonl``, the process exit code, and the side-channel the log lacks.

    ``session_id`` and ``model`` come from ``session.json`` at run time and from the stored
    ``result.json`` on replay. ``sub_transcripts`` is ``None`` for a captured log, where the
    transcripts are discovered under ``<session dir>/subagents/``.
    """

    def __init__(
        self, path: Path, exit_code: int, session_id: str, model: str, sub_transcripts: list[Path] | None = None
    ) -> None:
        super().__init__(path)
        self.exit_code = exit_code
        self.session_id = session_id
        self.model = model
        self.sub_transcripts = sub_transcripts

    def to_result(self, workspace: Path, files_written: list[str]) -> RunResult:
        """Fold this log into a run: one :class:`Call` per metered turn, credits only (ADR 0078)."""
        records = read_jsonl_numbered(self.path)
        ledger = fold(records, self.path.name)
        transcripts = self.sub_transcripts
        if transcripts is None:
            transcripts = sorted((self.path.parent / "subagents").glob("*.jsonl"))
        metered = sum(1 for c in ledger.calls if c.usage.credits)
        return RunResult.folded(
            ledger.calls,
            subagents_of(transcripts, records, ledger.calls, self.path.name),
            harness="kiro",
            model=self.model,
            session_id=self.session_id,
            session_log=str(self.path),
            workspace=str(workspace),
            exit_code=self.exit_code,
            duration_ms=ledger.duration_ms,
            final_text=ledger.calls[-1].text if ledger.calls else "",
            tool_calls=dict(ledger.tools),
            files_written=files_written,
            harness_reported_cost_usd=None,
            reported_usage={"requests": ledger.requests},
            reported_turns=metered,
            record_kinds=(kinds := KIRO.census([rec for _, rec in records])),
            compactions=record_kinds.compactions(kinds),
            api_duration_ms=ledger.duration_ms or None,
        )


# -- record classification -------------------------------------------------------------


def _classify(rec: dict[str, Any]) -> str:
    payload = rec.get("payload")
    if not isinstance(payload, dict):
        return "kiro/unknown"
    kind = str(payload.get("type") or "unknown")
    if kind == "assistant":
        return f"kiro/assistant/{str(payload.get('operationType') or 'unknown').lower()}"
    if kind == "session_event":
        return f"kiro/session_event/{payload.get('category') or 'unknown'}"
    if kind == "tombstone":
        return f"kiro/tombstone/{payload.get('kind') or 'unknown'}"
    return f"kiro/{kind}"


# -- the harness -----------------------------------------------------------------------


class KiroHarness(Harness):
    """``kiro-cli chat --v3``: no ``--session-id``, so a private KIRO_HOME isolates the session."""

    name = "kiro"
    shell_tools = frozenset({"run_command", "execute_bash", "execute_pwsh", "shell"})
    persistent_shells = frozenset()  # each command runs at its own ``cwd``
    efforts = KIRO_EFFORTS

    def invoke(self, *, skill: str, task: str) -> str:
        """``/<skill> <task>``: Kiro exposes every skill as a slash command, trailing text passed along.

        Kiro discovers skills under ``$KIRO_HOME/skills/<name>/SKILL.md``, where :func:`run_kiro`
        copies the skill under test, and "a skill named ``pr-review`` becomes the ``/pr-review``
        slash command" (kiro.dev/docs/skills, verified against kiro-cli 3.1.0; ADR 0044).
        """
        return f"/{skill} {task}"

    def effort_args(self, effort: str | None) -> list[str]:
        """``--effort <rung>``: a first-class flag on ``kiro-cli chat``."""
        return effort_argv(effort)

    def run(
        self,
        *,
        prompt: str,
        model: str,
        workspace: Path,
        effort: str | None = None,
        skill_dir: Path | None = None,
        timeout_s: int = DEFAULT_TIMEOUT_S,
    ) -> RunResult:  # pragma: no cover - spawns a real CLI (ADR 0002)
        return run_kiro(prompt, model, workspace, effort=effort, skill_dir=skill_dir, timeout_s=timeout_s)

    def session_from_capture(self, session: SessionDir, stored: dict[str, Any]) -> KiroSessionLog:
        """The log names neither its id nor its model, so both come back from the stored result."""
        return KiroSessionLog(
            session.log,
            int(stored.get("exit_code") or 0),
            str(stored.get("session_id") or ""),
            str(stored.get("model") or ""),
        )

    def classify_record(self, rec: dict[str, Any]) -> str:
        return _classify(rec)


KIRO = register(KiroHarness())
