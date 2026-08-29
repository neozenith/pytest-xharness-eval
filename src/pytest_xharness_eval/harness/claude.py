"""The Claude Code harness: how ``claude -p`` is invoked, and how its session log folds.

Claude Code writes ``<config>/projects/<cwd-slug>/<session-uuid>.jsonl`` with one record
per *content block*, so the records of a single API call share ``message.id`` and repeat
its ``usage``. The correlation contract is derivation, never search: the harness mints
the session UUID with ``--session-id``, so the log path is known before the process
starts and a mismatch is a hard failure.

The log alone is not the whole run. ``total_cost_usd``, the session id and the aggregate
usage exist only on the ``-p --output-format json`` stdout envelope. :class:`ClaudeSessionLog`
carries that envelope, which is why a replay from a captured directory reconstructs one
from the stored ``result.json`` *here* rather than in the replay module (ADR 0023).
"""

from __future__ import annotations

# Standard Library
import json
import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Our Libraries
from pytest_xharness_eval.harness import records as record_kinds
from pytest_xharness_eval.harness.base import (
    DEFAULT_TIMEOUT_S,
    Harness,
    RunError,
    SessionLog,
    register,
    spawn,
)
from pytest_xharness_eval.harness.normalise import (
    Numbered,
    join_text,
    read_jsonl_numbered,
    summarise,
    text_of,
)
from pytest_xharness_eval.model import workspace as ws
from pytest_xharness_eval.model.clock import ms_between
from pytest_xharness_eval.model.runresult import Call, RunResult, Subagent, ToolCall, ToolResult, Usage

if TYPE_CHECKING:
    # Our Libraries
    from pytest_xharness_eval.model.layout import SessionDir

# Isolation levers verified against the installed CLI (claude 2.1.237).
_ISOLATION = ["--setting-sources", ""]


# -- invocation ------------------------------------------------------------------------


def claude_log_path(config_dir: Path, workspace: Path, session_id: str) -> Path:
    """The correlation contract: derived, never searched.

    Claude slugifies the cwd by replacing EVERY non-alphanumeric character
    with ``-`` (verified 2026-08-21 against claude 2.1.237: underscores in
    the path also become dashes, not just slashes and dots).
    """
    slug = "".join(c if c.isalnum() else "-" for c in str(workspace.resolve()))
    return config_dir / "projects" / slug / f"{session_id}.jsonl"


def run_claude(
    prompt: str,
    model: str,
    workspace: Path,
    skill_dir: Path | None = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> RunResult:  # pragma: no cover - spawns a real CLI (ADR 0002)
    """Run ``claude -p`` in the workspace; return the normalised RunResult."""
    session_id = str(uuid.uuid4())
    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")))

    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--model",
        model,
        "--session-id",
        session_id,
        "--permission-mode",
        "bypassPermissions",
        *_ISOLATION,
    ]
    if skill_dir is not None:
        cmd += ["--add-dir", str(skill_dir)]

    before = ws.snapshot(workspace)
    proc = spawn(cmd, cwd=workspace, env=dict(os.environ), timeout_s=timeout_s)
    after = ws.snapshot(workspace)

    if proc.returncode != 0 and not proc.stdout.strip():
        raise RunError(f"claude exited {proc.returncode} with no result envelope: {proc.stderr[:2000]}")
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RunError(f"claude stdout was not the JSON envelope: {proc.stdout[:500]}") from exc

    log = claude_log_path(config_dir, workspace, session_id)
    if not log.is_file():
        raise RunError(f"claude session log not found at derived path: {log}")

    got = str(envelope.get("session_id") or "")
    if got != session_id:
        raise RunError(f"session id mismatch: harness minted {session_id}, envelope says {got}")

    return ClaudeSessionLog(log, envelope).to_result(workspace, ws.diff(before, after))


# -- folding the log -------------------------------------------------------------------


def _call_usage(u: dict[str, Any]) -> Usage:
    creation = u.get("cache_creation") or {}
    return Usage(
        input_tokens=int(u.get("input_tokens") or 0),
        output_tokens=int(u.get("output_tokens") or 0),
        cache_read_tokens=int(u.get("cache_read_input_tokens") or 0),
        cache_write_tokens=int(u.get("cache_creation_input_tokens") or 0),
        reasoning_tokens=int((u.get("output_tokens_details") or {}).get("thinking_tokens") or 0),
        cache_write_1h_tokens=int(creation.get("ephemeral_1h_input_tokens") or 0),
        cache_write_5m_tokens=int(creation.get("ephemeral_5m_input_tokens") or 0),
    )


class _Ledger:
    """Fold Claude's per-block records into per-message calls.

    Turn boundaries (ADR 0023): Claude Code writes each content block of a message as
    its own record and appends a tool's result record the moment that tool finishes,
    so the results of a turn's early tools land *between* that turn's later blocks.
    A tool result therefore belongs to the turn that issued the tool (matched by
    ``tool_use_id``), and any other record belongs to the turn in progress. Records
    before the first call belong to the first call. The outcome is one contiguous,
    monotonic line range per turn, in the order the log wrote them.

    ``results_in`` keeps its own meaning: the results that entered a call's context,
    which are the previous turn's results.
    """

    def __init__(self) -> None:
        self.calls: list[Call] = []
        self.tools: dict[str, int] = {}
        self._by_id: dict[str, Call] = {}
        self._tool_names: dict[str, str] = {}  # tool_use_id -> tool name
        self._tool_owner: dict[str, Call] = {}  # tool_use_id -> the call that issued it
        self._pending: list[ToolResult] = []
        self._pending_lines: list[int] = []
        self._last_ts: str | None = None  # timestamp of the previous record, for per-call latency

    def seen(self, rec: dict[str, Any]) -> None:
        """Remember the record's timestamp after it has been folded, for the next call's latency."""
        self._last_ts = str(rec.get("timestamp") or self._last_ts or "") or None

    def _attribute(self, line: int, owner: Call | None = None) -> None:
        target = owner or (self.calls[-1] if self.calls else None)
        if target is None:
            self._pending_lines.append(line)
        elif not target.records or target.records[-1] != line:
            target.records.append(line)

    def other(self, line: int) -> None:
        """A harness record belongs to the turn in progress."""
        self._attribute(line)

    def user(self, line: int, rec: dict[str, Any]) -> None:
        content = (rec.get("message") or {}).get("content")
        owner: Call | None = None
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    tool_use_id = str(block.get("tool_use_id") or "")
                    text = text_of(block.get("content"))
                    tool = self._tool_names.get(tool_use_id, "unknown")
                    self._pending.append(ToolResult(tool=tool, chars=len(text), content=text))
                    owner = owner or self._tool_owner.get(tool_use_id)
        self._attribute(line, owner)

    def assistant(self, line: int, rec: dict[str, Any]) -> None:
        msg = rec.get("message") or {}
        if record_kinds.is_synthetic(msg):
            # Not a model call: Claude Code's own "API Error ..." notice. Evidence, not a turn.
            self._attribute(line)
            return
        mid = str(msg.get("id") or f"anon-{len(self.calls)}")
        call = self._by_id.get(mid)
        if call is None:
            call = Call(
                n=len(self.calls) + 1,
                at=str(rec.get("timestamp") or ""),
                usage=_call_usage(msg.get("usage") or {}),
                stop_reason=str(msg.get("stop_reason") or ""),
                results_in=self._pending,
                records=self._pending_lines,
                latency_ms=ms_between(self._last_ts, str(rec.get("timestamp") or "")),
            )
            self._pending, self._pending_lines = [], []
            self._by_id[mid] = call
            self.calls.append(call)
        self._attribute(line, call)
        for block in msg.get("content") or []:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "tool_use":
                name = str(block.get("name") or "unknown")
                self.tools[name] = self.tools.get(name, 0) + 1
                self._tool_names[str(block.get("id") or "")] = name
                self._tool_owner[str(block.get("id") or "")] = call
                call.tools.append(
                    ToolCall(
                        name=name,
                        summary=summarise(name, block.get("input")),
                        input=block.get("input"),
                        id=str(block.get("id") or ""),
                    )
                )
            elif kind == "text":
                call.text = join_text(call.text, str(block.get("text") or ""))
            elif kind == "thinking":
                call.thinking = join_text(call.thinking, str(block.get("thinking") or ""))

    def finish(self) -> None:
        """Records are attributed as they arrive; only a log with no call at all leaves lines pending."""
        if self.calls and self._pending_lines:
            self.calls[-1].records.extend(self._pending_lines)
            self._pending_lines = []
        for call in self.calls:
            call.records.sort()


def ledger_of(records: Numbered) -> tuple[list[Call], dict[str, int]]:
    """One Call per ``message.id``, tool calls counted across every record."""
    ledger = _Ledger()
    for line, rec in records:
        rtype = rec.get("type")
        if rtype == "user":
            ledger.user(line, rec)
        elif rtype == "assistant":
            ledger.assistant(line, rec)
        else:
            ledger.other(line)
        ledger.seen(rec)
    ledger.finish()
    return ledger.calls, ledger.tools


def _context_window(envelope: dict[str, Any], model: str) -> int | None:
    """``modelUsage[<model>].contextWindow`` from the envelope, matched exactly or by prefix."""
    usage = envelope.get("modelUsage") or {}
    for key, value in usage.items():
        if isinstance(value, dict) and (key == model or key.startswith(model) or model.startswith(key)):
            window = value.get("contextWindow")
            if isinstance(window, int):
                return window
    return None


class ClaudeSessionLog(SessionLog):
    """A Claude session log and the stdout envelope that completes it.

    The envelope is not an optional extra: the session id, ``total_cost_usd`` and the
    aggregate usage appear nowhere in the log, so a log without one cannot be folded.
    Holding it here is what lets :meth:`to_result` share a signature with every other
    dialect.
    """

    def __init__(self, path: Path, envelope: dict[str, Any]) -> None:
        super().__init__(path)
        self.envelope = envelope

    def to_result(self, workspace: Path, files_written: list[str]) -> RunResult:
        """Fold this log and its envelope into a run: one :class:`Call` per ``message.id``."""
        envelope = self.envelope
        records = read_jsonl_numbered(self.path)
        calls, tools = ledger_of(records)

        model = ""
        for _, rec in records:
            msg = rec.get("message") or {}
            if rec.get("type") == "assistant" and not record_kinds.is_synthetic(msg):
                model = str(msg.get("model") or model)

        env_usage = envelope.get("usage") or {}
        reported = {k: int(v) for k, v in env_usage.items() if isinstance(v, int | float) and not isinstance(v, bool)}
        num_turns = envelope.get("num_turns")
        model_id = model or str(envelope.get("model") or "")
        ttft = envelope.get("ttft_ms")
        api_ms = envelope.get("duration_api_ms")
        spawns = {tool.id: call.n for call in calls for tool in call.tools if tool.id}

        return RunResult.folded(
            calls,
            subagents_of(self.path, spawns),
            harness="claude",
            model=model_id,
            session_id=str(envelope.get("session_id") or ""),
            session_log=str(self.path),
            workspace=str(workspace),
            exit_code=1 if envelope.get("is_error") else 0,
            duration_ms=int(envelope.get("duration_ms") or 0),
            final_text=str(envelope.get("result") or ""),
            tool_calls=tools,
            files_written=files_written,
            harness_reported_cost_usd=envelope.get("total_cost_usd"),
            reported_usage=reported,
            reported_turns=int(num_turns) if num_turns is not None else None,
            reported_model_usage=dict(envelope.get("modelUsage") or {}),
            envelope={k: v for k, v in envelope.items() if k != "result"},
            record_kinds=CLAUDE.census([rec for _, rec in records]),
            context_window=_context_window(envelope, model_id),
            ttft_ms=int(ttft) if isinstance(ttft, int | float) else None,
            api_duration_ms=int(api_ms) if isinstance(api_ms, int | float) else None,
        )


def subagents_of(log: Path, spawns: dict[str, int]) -> list[Subagent]:
    """Fold every subagent transcript beside a Claude session log.

    Native layout: ``<config>/projects/<slug>/<session-id>/subagents/agent-<id>.jsonl``,
    each with an ``agent-<id>.meta.json`` sidecar naming the agent type, the spawn
    description, and the ``toolUseId`` of the Agent tool call that spawned it. Captured
    layout: the same pairs under ``<session dir>/subagents/``. ``spawns`` maps tool-use
    id -> the primary turn that issued it; the transcripts are the same record dialect
    as the session log, so :func:`ledger_of` folds them unchanged.
    """
    directory = next(
        (d for d in (log.parent / "subagents", log.with_suffix("") / "subagents") if d.is_dir()),
        None,
    )
    if directory is None:
        return []
    subs: list[Subagent] = []
    for transcript in sorted(directory.glob("agent-*.jsonl")):
        meta: dict[str, Any] = {}
        sidecar = transcript.with_name(f"{transcript.stem}.meta.json")
        if sidecar.is_file():
            try:
                meta = json.loads(sidecar.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                meta = {}
        records = read_jsonl_numbered(transcript)
        calls, _tools = ledger_of(records)
        agent_id = str((records[0][1].get("agentId") if records else "") or transcript.stem.removeprefix("agent-"))
        subs.append(
            Subagent.folded(
                calls,
                agent=str(meta.get("agentType") or "subagent"),
                id=agent_id,
                log=str(transcript),
                parent_turn=spawns.get(str(meta.get("toolUseId") or "")),
                description=str(meta.get("description") or ""),
            )
        )
    return subs


# -- record classification -------------------------------------------------------------


def _classify(rec: dict[str, Any]) -> str:
    rtype = str(rec.get("type") or "unknown")
    if rtype == "user":
        content = (rec.get("message") or {}).get("content")
        if not isinstance(content, str) and "tool_result" in record_kinds.block_types(content):
            return "claude/user/tool_result"
        return (
            "claude/user/injected"
            if record_kinds.leading_tag(record_kinds.message_text(content))
            else "claude/user/prompt"
        )
    if rtype == "assistant":
        msg = rec.get("message") or {}
        if record_kinds.is_synthetic(msg):
            return "claude/assistant/synthetic"
        kinds = record_kinds.block_types(msg.get("content"))
        if "tool_use" in kinds:
            return "claude/assistant/tool_use"
        if "thinking" in kinds and "text" not in kinds:
            return "claude/assistant/thinking"
        return "claude/assistant/text"
    if rtype == "attachment":
        return f"claude/attachment/{(rec.get('attachment') or {}).get('type') or 'unknown'}"
    return f"claude/{rtype}"


# -- the harness -----------------------------------------------------------------------


class ClaudeHarness(Harness):
    """``claude -p``: the session id is minted by the harness, so the log path is derived."""

    name = "claude"
    shell_tools = frozenset({"Bash"})
    persistent_shells = frozenset({"Bash"})  # one shell process spans the session, so ``cd`` sticks

    def run(
        self,
        *,
        prompt: str,
        model: str,
        workspace: Path,
        skill_dir: Path | None = None,
        timeout_s: int = DEFAULT_TIMEOUT_S,
    ) -> RunResult:  # pragma: no cover - spawns a real CLI (ADR 0002)
        return run_claude(prompt, model, workspace, skill_dir=skill_dir, timeout_s=timeout_s)

    def session_from_capture(self, session: SessionDir, stored: dict[str, Any]) -> ClaudeSessionLog:
        """Rebuild the envelope from the stored result, then fold as the live run did.

        The captured ``result.json`` keeps the envelope minus its ``result`` text (which
        lives on ``final_text``), so replay restores that text and the three fields the
        writer lifted out of it. This reconstruction belongs to the Claude dialect: it is
        the price of a log that is not self-contained, and no other module should know it.
        """
        envelope = dict(stored.get("envelope") or {})
        envelope.setdefault("session_id", stored.get("session_id"))
        envelope.setdefault("total_cost_usd", stored.get("harness_reported_cost_usd"))
        envelope.setdefault("duration_ms", stored.get("duration_ms"))
        envelope["result"] = stored.get("final_text") or ""
        return ClaudeSessionLog(session.log, envelope)

    def classify_record(self, rec: dict[str, Any]) -> str:
        return _classify(rec)


CLAUDE = register(ClaudeHarness())
