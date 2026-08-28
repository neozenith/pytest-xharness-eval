"""The Codex harness: how ``codex exec`` is invoked, and how its rollout folds.

Codex writes ``$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl`` with one
``token_count`` event per model call, carrying ``last_token_usage`` (that call) and
``total_token_usage`` (cumulative). There is no ``--session-id``, so the correlation
contract is isolation instead of derivation: ``CODEX_HOME`` points at a private per-run
directory seeded with the credential files, and exactly one primary rollout can then
exist under it (ADR 0005). A spawned subagent forks its own rollout beside it, so
"exactly one primary" is checked rather than assumed.

A rollout is self-contained -- the session id, model, timing and usage are all in it --
but it records no process exit code. That is the side-channel :class:`CodexSessionLog`
carries, and it is why a replay needs nothing from the stored ``result.json`` but that
one integer.
"""

from __future__ import annotations

# Standard Library
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

# Our Libraries
from pytest_xharness_eval import records as record_kinds
from pytest_xharness_eval import workspace as ws
from pytest_xharness_eval.harness.base import (
    DEFAULT_TIMEOUT_S,
    Harness,
    RunError,
    SessionLog,
    register,
    spawn,
)
from pytest_xharness_eval.normalise import (
    Numbered,
    attach_subagents,
    join_text,
    ms_between,
    read_jsonl_numbered,
    sum_usage,
    summarise,
    text_of,
)
from pytest_xharness_eval.runresult import Call, RunResult, Subagent, ToolCall, ToolResult, Usage

# Isolation levers verified against the installed CLI (codex 0.148.0).
_ISOLATION = ["--ignore-user-config", "--skip-git-repo-check"]

# Credential material Codex keeps inside CODEX_HOME (ADR 0005, risk accepted).
_CRED_FILES = ["auth.json", ".credentials.json", "config.toml"]

# Codex item types that represent the agent acting rather than talking.
_TOOL_ITEMS = {"CommandExecution", "FileChange", "Extension"}
_CALL_ITEMS = {"custom_tool_call", "function_call"}
_OUTPUT_ITEMS = {"custom_tool_call_output", "function_call_output"}


# -- invocation ------------------------------------------------------------------------


def _seed_home(run_dir: Path) -> Path:  # pragma: no cover - reads real credentials (ADR 0002)
    real_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    private = run_dir / "codex_home"
    private.mkdir(parents=True, exist_ok=True)
    seeded = False
    for name in _CRED_FILES:
        src = real_home / name
        if src.is_file():
            shutil.copy2(src, private / name)
            seeded = True
    if not seeded:
        raise RunError(f"no codex credentials found under {real_home} to seed a private home")
    return private


def _rollout_is_subagent(rollout: Path) -> bool:
    """A rollout another thread spawned: Codex subagents fork their own rollout files.

    The primary session's ``session_meta`` carries ``source: "exec"``; a subagent's
    carries ``source: {"subagent": {"thread_spawn": {...}}}`` and ``forked_from_id``
    naming the primary. An unreadable first line counts as primary, so a schema drift
    surfaces as "more than one primary" rather than silently dropping a candidate.
    """
    try:
        first = json.loads(rollout.read_text(encoding="utf-8").split("\n", 1)[0])
    except (OSError, json.JSONDecodeError, IndexError):
        return False
    payload = first.get("payload") if isinstance(first, dict) else None
    if not isinstance(payload, dict):
        return False
    source = payload.get("source")
    return bool(payload.get("forked_from_id")) or (isinstance(source, dict) and "subagent" in source)


def primary_rollout(rollouts: list[Path]) -> Path:
    """The one rollout that is the session itself, among any its subagents forked.

    A single ``codex exec`` writes one rollout per thread: the primary plus one per
    spawned subagent. The session log the harness captures is the primary's; anything
    other than exactly one primary is a hard failure, never a guess (the evidence
    contract: a mismatched session log must fail loudly).
    """
    primaries = [r for r in rollouts if not _rollout_is_subagent(r)]
    if len(primaries) != 1:
        names = ", ".join(r.name for r in rollouts)
        raise RunError(
            f"expected exactly one primary rollout under private CODEX_HOME, "
            f"found {len(primaries)} of {len(rollouts)} ({names})"
        )
    return primaries[0]


def run_codex(
    prompt: str,
    model: str,
    workspace: Path,
    skill_dir: Path | None = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> RunResult:  # pragma: no cover - spawns a real CLI (ADR 0002)
    """Run ``codex exec`` under a private CODEX_HOME; return the normalised RunResult."""
    run_dir = workspace.parent / f"{workspace.name}.codex"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    private_home = _seed_home(run_dir)

    if skill_dir is not None:
        dest = private_home / "skills" / skill_dir.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(skill_dir, dest)

    env = {**os.environ, "CODEX_HOME": str(private_home)}
    cmd = [
        "codex",
        "exec",
        prompt,
        "--model",
        model,
        "--json",
        "-C",
        str(workspace),
        "--sandbox",
        "workspace-write",
        *_ISOLATION,
    ]

    before = ws.snapshot(workspace)
    start = time.monotonic()
    proc = spawn(cmd, cwd=workspace, env=env, timeout_s=timeout_s)
    wall_ms = int((time.monotonic() - start) * 1000)
    after = ws.snapshot(workspace)

    rollouts = sorted((private_home / "sessions").rglob("rollout-*.jsonl"))
    if not rollouts:
        raise RunError(f"no rollout under private CODEX_HOME; codex exited {proc.returncode}: {proc.stderr[:2000]}")
    rollout = primary_rollout(rollouts)

    session = CodexSessionLog(rollout, proc.returncode, sub_rollouts=[r for r in rollouts if r != rollout])
    result = session.to_result(workspace, ws.diff(before, after))
    if not result.duration_ms:
        result.duration_ms = wall_ms
    if not result.session_id:
        raise RunError(f"rollout {rollouts[0]} carries no session_meta id")
    return result


# -- folding the rollout ---------------------------------------------------------------


def _call_usage(last: dict[str, Any]) -> Usage:
    """OpenAI's ``input_tokens`` is the whole prompt; ``cached_input_tokens`` and
    ``cache_write_input_tokens`` are *subsets* of it (``input_tokens_details`` in the
    Responses API). Anthropic reports the three tiers disjointly. Split Codex's figure
    so each tier prices once and ``context_tokens`` (the tiers summed) is the prompt
    again. See docs/token-accounting.md.
    """
    cached = int(last.get("cached_input_tokens") or 0)
    written = int(last.get("cache_write_input_tokens") or 0)
    raw_input = int(last.get("input_tokens") or 0)
    return Usage(
        input_tokens=max(raw_input - cached - written, 0),
        output_tokens=int(last.get("output_tokens") or 0),
        cache_read_tokens=cached,
        cache_write_tokens=written,
        reasoning_tokens=int(last.get("reasoning_output_tokens") or 0),
    )


class _Ledger:
    """Fold a Codex rollout into per-``token_count`` calls.

    Order in the rollout is: the model's response items (reasoning, message, tool
    calls), then the tool outputs, then the ``token_count`` for that call. So the
    tool calls before a count belong to that call, and the outputs before it enter
    the *next* call's context.
    """

    def __init__(self) -> None:
        self.calls: list[Call] = []
        self.tools: dict[str, int] = {}
        self.last_total: dict[str, Any] = {}
        self._tool_calls: list[ToolCall] = []
        self._outputs: list[ToolResult] = []
        self._carried: list[ToolResult] = []
        self._text: str = ""
        self._thinking: str = ""
        self._lines: list[int] = []
        self._call_names: dict[str, str] = {}  # call_id -> tool name
        self.context_window: int | None = None
        self.tasks = 0
        self.duration_ms = 0
        self.final_text = ""
        self.ttft_ms: int | None = None
        self._boundary_ts: str | None = None  # task_started or the previous token_count: where this call's clock starts

    def line(self, line: int) -> None:
        self._lines.append(line)

    def started(self, at: str, payload: dict[str, Any]) -> None:
        self._boundary_ts = at or self._boundary_ts
        window = payload.get("model_context_window")
        if isinstance(window, int):
            self.context_window = window

    def response_item(self, p: dict[str, Any]) -> None:
        ptype = p.get("type")
        if ptype in _CALL_ITEMS:
            name = str(p.get("name") or ptype)
            self._call_names[str(p.get("call_id") or "")] = name
            args = p.get("input") if "input" in p else p.get("arguments")
            self._tool_calls.append(
                ToolCall(name=name, summary=summarise(name, args), input=args, id=str(p.get("call_id") or ""))
            )
        elif ptype in _OUTPUT_ITEMS:
            text = text_of(p.get("output"))
            tool = self._call_names.get(str(p.get("call_id") or ""), "unknown")
            self._outputs.append(ToolResult(tool=tool, chars=len(text), content=text))
        elif ptype == "message" and p.get("role") == "assistant":
            self._text = join_text(self._text, text_of(p.get("content")))
        elif ptype == "reasoning":
            summary = p.get("summary") or p.get("content") or []
            self._thinking = join_text(self._thinking, text_of(summary))

    def token_count(self, at: str, info: dict[str, Any]) -> None:
        last = info.get("last_token_usage") or {}
        total = info.get("total_token_usage") or {}
        if not last and not total:
            return
        if not last:
            # Older rollouts carry only the cumulative figure; this call is the step since the last one.
            last = {k: int(v) - int(self.last_total.get(k) or 0) for k, v in total.items() if isinstance(v, int)}
        if total:
            self.last_total = total
        window = info.get("model_context_window")
        if isinstance(window, int):
            self.context_window = window
        self.calls.append(
            Call(
                n=len(self.calls) + 1,
                at=at,
                usage=_call_usage(last),
                stop_reason="tool_use" if self._tool_calls else "end_turn",
                text=self._text,
                thinking=self._thinking,
                tools=self._tool_calls,
                results_in=self._carried,
                records=self._lines,
                latency_ms=ms_between(self._boundary_ts, at),
            )
        )
        self._boundary_ts = at or self._boundary_ts
        self._carried, self._outputs = self._outputs, []
        self._tool_calls, self._text, self._thinking, self._lines = [], "", "", []

    def item_completed(self, item: dict[str, Any]) -> None:
        kind = item.get("item_type") or item.get("type") or ""
        if kind in _TOOL_ITEMS:
            self.tools[kind] = self.tools.get(kind, 0) + 1

    def event(self, rec: dict[str, Any], payload: dict[str, Any]) -> None:
        """Route one ``event_msg`` record to the handler for its payload type."""
        ptype = payload.get("type")
        at = str(rec.get("timestamp") or "")
        if ptype == "token_count":
            self.token_count(at, payload.get("info") or {})
        elif ptype == "task_started":
            self.started(at, payload)
        elif ptype == "task_complete":
            self.tasks += 1
            self.duration_ms += int(payload.get("duration_ms") or 0)
            self.final_text = str(payload.get("last_agent_message") or self.final_text)
            first_token = payload.get("time_to_first_token_ms")
            if isinstance(first_token, int | float) and self.ttft_ms is None:
                self.ttft_ms = int(first_token)
        elif ptype == "item_completed":
            self.item_completed(payload.get("item") or {})

    def finish(self) -> None:
        if self.calls and self._lines:
            self.calls[-1].records.extend(self._lines)
            self._lines = []


def fold(records: Numbered) -> tuple[str, str, _Ledger]:
    """Fold one rollout's records into a ledger; returns (session id, model, ledger)."""
    session_id = ""
    model = ""
    ledger = _Ledger()
    for line, rec in records:
        ledger.line(line)
        rtype = rec.get("type")
        payload = rec.get("payload") or {}
        if rtype == "session_meta":
            session_id = str(payload.get("id") or session_id)
        elif rtype == "turn_context":
            model = str(payload.get("model") or model)
        elif rtype == "response_item":
            ledger.response_item(payload)
        elif rtype == "event_msg":
            ledger.event(rec, payload)
    ledger.finish()
    return session_id, model, ledger


def from_codex(
    log: Path,
    exit_code: int,
    workspace: Path,
    files_written: list[str],
    sub_rollouts: list[Path] | None = None,
) -> RunResult:
    """Normalise a Codex rollout file.

    ``sub_rollouts`` are the forked subagent rollouts of the same run (the runner passes
    them from the private ``CODEX_HOME``); ``None`` means discover them beside a captured
    log, under ``<session dir>/subagents/``.
    """
    records = read_jsonl_numbered(log)
    session_id, model, ledger = fold(records)

    total = ledger.last_total
    reported = {k: int(v) for k, v in total.items() if isinstance(v, int | float) and not isinstance(v, bool)}

    result = RunResult(
        harness="codex",
        model=model,
        session_id=session_id,
        session_log=str(log),
        workspace=str(workspace),
        exit_code=exit_code,
        duration_ms=ledger.duration_ms,
        turns=len(ledger.calls),
        final_text=ledger.final_text,
        usage=sum_usage(ledger.calls),
        tool_calls=ledger.tools,
        files_written=files_written,
        harness_reported_cost_usd=None,
        calls=ledger.calls,
        reported_usage=reported,
        reported_turns=ledger.tasks,
        record_kinds=CODEX.census([rec for _, rec in records]),
        context_window=ledger.context_window,
        ttft_ms=ledger.ttft_ms,
        api_duration_ms=ledger.duration_ms or None,
    )
    if sub_rollouts is None:
        sub_rollouts = sorted((log.parent / "subagents").glob("*.jsonl"))
    return attach_subagents(result, subagents_of(sub_rollouts, result.calls))


def subagents_of(rollouts: list[Path], primary_calls: list[Call]) -> list[Subagent]:
    """Fold each forked rollout into a subagent ledger.

    A sub-rollout's ``session_meta`` carries the spawn (``source.subagent.thread_spawn``:
    nickname, agent path) and its timestamp. The primary turn that owns it is the first
    call measured at or after that moment — a turn's tool calls run before its
    ``token_count`` is written — else the last turn.
    """
    subs: list[Subagent] = []
    for rollout in rollouts:
        records = read_jsonl_numbered(rollout)
        meta: dict[str, Any] = {}
        spawn_at = ""
        for _, rec in records:
            if rec.get("type") == "session_meta":
                meta = rec.get("payload") or {}
                spawn_at = str(rec.get("timestamp") or meta.get("timestamp") or "")
                break
        session_id, _model, ledger = fold(records)
        parent = next(
            (c.n for c in primary_calls if spawn_at and c.at and c.at >= spawn_at),
            primary_calls[-1].n if primary_calls else None,
        )
        subs.append(
            Subagent(
                agent=str(meta.get("agent_nickname") or "subagent"),
                id=session_id or str(meta.get("id") or ""),
                log=str(rollout),
                parent_turn=parent,
                turns=len(ledger.calls),
                description=str(meta.get("agent_path") or ""),
                usage=sum_usage(ledger.calls),
                calls=ledger.calls,
            )
        )
    return subs


# -- record classification -------------------------------------------------------------


def _classify(rec: dict[str, Any]) -> str:
    rtype = str(rec.get("type") or "unknown")
    payload = rec.get("payload") or {}
    if rtype == "response_item":
        sub = str(payload.get("type") or "unknown")
        if sub == "message":
            role = str(payload.get("role") or "unknown")
            injected = role == "user" and record_kinds.leading_tag(record_kinds.message_text(payload.get("content")))
            return f"codex/response_item/message/{role}{'/injected' if injected else ''}"
        return f"codex/response_item/{sub}"
    if rtype == "event_msg":
        sub = str(payload.get("type") or "unknown")
        if sub == "item_completed":
            item = payload.get("item") or {}
            kind = str(item.get("item_type") or item.get("type") or "unknown")
            injected = kind == "UserMessage" and record_kinds.leading_tag(
                record_kinds.message_text(item.get("content"))
            )
            return f"codex/event_msg/item_completed/{kind}{'/injected' if injected else ''}"
        return f"codex/event_msg/{sub}"
    return f"codex/{rtype}"


# -- the harness -----------------------------------------------------------------------


class CodexSessionLog(SessionLog):
    """A Codex rollout, the process exit code, and the subagent rollouts forked beside it.

    The rollout carries its own session id, model, timing and usage, so the only thing it
    cannot know is how the process ended. ``sub_rollouts`` is ``None`` for a captured log,
    where the forks are discovered under ``<session dir>/subagents/``.
    """

    def __init__(self, path: Path, exit_code: int, sub_rollouts: list[Path] | None = None) -> None:
        super().__init__(path)
        self.exit_code = exit_code
        self.sub_rollouts = sub_rollouts

    def to_result(self, workspace: Path, files_written: list[str]) -> RunResult:
        return from_codex(self.path, self.exit_code, workspace, files_written, sub_rollouts=self.sub_rollouts)


class CodexHarness(Harness):
    """``codex exec``: no ``--session-id``, so a private CODEX_HOME isolates the rollout."""

    name = "codex"
    shell_tools = frozenset({"exec", "shell", "CommandExecution", "bash", "exec_command"})
    persistent_shells = frozenset()  # every exec runs in its own process at ``workdir``

    def run(
        self,
        *,
        prompt: str,
        model: str,
        workspace: Path,
        skill_dir: Path | None = None,
        timeout_s: int = DEFAULT_TIMEOUT_S,
    ) -> RunResult:  # pragma: no cover - spawns a real CLI (ADR 0002)
        return run_codex(prompt, model, workspace, skill_dir=skill_dir, timeout_s=timeout_s)

    def session_from_capture(self, session_dir: Path, stored: dict[str, Any]) -> CodexSessionLog:
        """The rollout is self-contained; only the exit code has to come from the stored result."""
        return CodexSessionLog(session_dir / "log.jsonl", int(stored.get("exit_code") or 0))

    def classify_record(self, rec: dict[str, Any]) -> str:
        return _classify(rec)


CODEX = register(CodexHarness())
