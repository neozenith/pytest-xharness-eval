"""Turn each CLI's session log into one RunResult with a per-call ledger (ADR 0019, ADR 0021).

The two dialects differ fundamentally:

* Claude writes ``~/.claude/projects/<cwd-slug>/<session-uuid>.jsonl`` with one
  record per content block; records of one API call share ``message.id`` and
  repeat its ``usage`` block. ``total_cost_usd`` exists only on the
  ``-p --output-format json`` stdout envelope, never in the log.
* Codex writes ``$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl``
  with one ``token_count`` event per model call carrying ``last_token_usage``
  (that call) and ``total_token_usage`` (cumulative), and no cost anywhere.

Both adapters build the same ledger: one :class:`Call` per model API call, with
the tool calls it issued, the tool results that entered its context, its text
and thinking, and the log line numbers it was built from. Nothing is truncated:
the ledger is the evidence, and the report renders all of it. The run's
``usage`` is the ledger's sum and ``turns`` is its length; the CLI's own
aggregates are kept on ``reported_usage`` / ``reported_turns`` for reconciliation.
"""

from __future__ import annotations

# Standard Library
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

# Our Libraries
from pytest_xharness_eval import records as record_kinds
from pytest_xharness_eval.runresult import Call, RunResult, ToolCall, ToolResult, Usage

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path

# Codex item types that represent the agent acting rather than talking.
_CODEX_TOOL_ITEMS = {"CommandExecution", "FileChange", "Extension"}
_CODEX_CALL_ITEMS = {"custom_tool_call", "function_call"}
_CODEX_OUTPUT_ITEMS = {"custom_tool_call_output", "function_call_output"}

SUMMARY_CHARS = 120

Numbered = list[tuple[int, dict[str, Any]]]


def read_jsonl_numbered(path: Path) -> Numbered:
    """Parse a JSONL file into ``(line_number, record)`` pairs, skipping blank and unparseable lines.

    Line numbers are 1-based positions in the file, so a ledger can point back at
    the exact evidence it was built from.
    """
    out: Numbered = []
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            out.append((n, json.loads(line)))
        except json.JSONDecodeError:
            continue
    return out


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Parse a JSONL file, skipping blank and unparseable lines."""
    return [rec for _, rec in read_jsonl_numbered(path)]


def _text_of(content: Any) -> str:
    """Flatten a content value (string, list of blocks, or other JSON) to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("output") or ""))
            else:
                parts.append(str(block))
        return "\n".join(p for p in parts if p)
    return json.dumps(content) if content is not None else ""


def _summary(name: str, arguments: Any) -> str:
    """A one-line description of a tool call: its most telling argument, truncated for tables only."""
    if isinstance(arguments, str):
        text = arguments
    elif isinstance(arguments, dict):
        for key in ("file_path", "command", "skill", "cmd", "path", "pattern"):
            if key in arguments:
                text = str(arguments[key])
                break
        else:
            text = json.dumps(arguments)
    else:
        text = json.dumps(arguments)
    first = text.strip().split("\n", 1)[0]
    return first[:SUMMARY_CHARS]


def _join(existing: str, more: str) -> str:
    return (existing + "\n" + more).strip() if more else existing


def _ms_between(earlier: str | None, later: str | None) -> int | None:
    """Milliseconds between two ISO-8601 timestamps (``Z`` accepted); None if either is missing or unparseable."""
    if not earlier or not later:
        return None
    try:
        a = datetime.fromisoformat(earlier.replace("Z", "+00:00"))
        b = datetime.fromisoformat(later.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(int((b - a).total_seconds() * 1000), 0)


def _sum(calls: list[Call]) -> Usage:
    total = Usage()
    for call in calls:
        total.add(call.usage)
    return total


# -- Claude ----------------------------------------------------------------------


def _claude_call_usage(u: dict[str, Any]) -> Usage:
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


class _ClaudeLedger:
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
                    text = _text_of(block.get("content"))
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
                usage=_claude_call_usage(msg.get("usage") or {}),
                stop_reason=str(msg.get("stop_reason") or ""),
                results_in=self._pending,
                records=self._pending_lines,
                latency_ms=_ms_between(self._last_ts, str(rec.get("timestamp") or "")),
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
                    ToolCall(name=name, summary=_summary(name, block.get("input")), input=block.get("input"))
                )
            elif kind == "text":
                call.text = _join(call.text, str(block.get("text") or ""))
            elif kind == "thinking":
                call.thinking = _join(call.thinking, str(block.get("thinking") or ""))

    def finish(self) -> None:
        """Records are attributed as they arrive; only a log with no call at all leaves lines pending."""
        if self.calls and self._pending_lines:
            self.calls[-1].records.extend(self._pending_lines)
            self._pending_lines = []
        for call in self.calls:
            call.records.sort()


def claude_ledger(records: Numbered) -> tuple[list[Call], dict[str, int]]:
    """One Call per ``message.id``, tool calls counted across every record."""
    ledger = _ClaudeLedger()
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


def _claude_context_window(envelope: dict[str, Any], model: str) -> int | None:
    """``modelUsage[<model>].contextWindow`` from the envelope, matched exactly or by prefix."""
    usage = envelope.get("modelUsage") or {}
    for key, value in usage.items():
        if isinstance(value, dict) and (key == model or key.startswith(model) or model.startswith(key)):
            window = value.get("contextWindow")
            if isinstance(window, int):
                return window
    return None


def from_claude(log: Path, envelope: dict[str, Any], workspace: Path, files_written: list[str]) -> RunResult:
    """Normalise a Claude session log plus its stdout result envelope."""
    records = read_jsonl_numbered(log)
    calls, tools = claude_ledger(records)

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

    return RunResult(
        harness="claude",
        model=model or str(envelope.get("model") or ""),
        session_id=str(envelope.get("session_id") or ""),
        session_log=str(log),
        workspace=str(workspace),
        exit_code=1 if envelope.get("is_error") else 0,
        duration_ms=int(envelope.get("duration_ms") or 0),
        turns=len(calls),
        final_text=str(envelope.get("result") or ""),
        usage=_sum(calls),
        tool_calls=tools,
        files_written=files_written,
        harness_reported_cost_usd=envelope.get("total_cost_usd"),
        calls=calls,
        reported_usage=reported,
        reported_turns=int(num_turns) if num_turns is not None else None,
        reported_model_usage=dict(envelope.get("modelUsage") or {}),
        envelope={k: v for k, v in envelope.items() if k != "result"},
        record_kinds=record_kinds.census("claude", [rec for _, rec in records]),
        context_window=_claude_context_window(envelope, model_id),
        ttft_ms=int(ttft) if isinstance(ttft, int | float) else None,
        api_duration_ms=int(api_ms) if isinstance(api_ms, int | float) else None,
    )


# -- Codex -----------------------------------------------------------------------


def _codex_call_usage(last: dict[str, Any]) -> Usage:
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


class _CodexLedger:
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
        if ptype in _CODEX_CALL_ITEMS:
            name = str(p.get("name") or ptype)
            self._call_names[str(p.get("call_id") or "")] = name
            args = p.get("input") if "input" in p else p.get("arguments")
            self._tool_calls.append(ToolCall(name=name, summary=_summary(name, args), input=args))
        elif ptype in _CODEX_OUTPUT_ITEMS:
            text = _text_of(p.get("output"))
            tool = self._call_names.get(str(p.get("call_id") or ""), "unknown")
            self._outputs.append(ToolResult(tool=tool, chars=len(text), content=text))
        elif ptype == "message" and p.get("role") == "assistant":
            self._text = _join(self._text, _text_of(p.get("content")))
        elif ptype == "reasoning":
            summary = p.get("summary") or p.get("content") or []
            self._thinking = _join(self._thinking, _text_of(summary))

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
                usage=_codex_call_usage(last),
                stop_reason="tool_use" if self._tool_calls else "end_turn",
                text=self._text,
                thinking=self._thinking,
                tools=self._tool_calls,
                results_in=self._carried,
                records=self._lines,
                latency_ms=_ms_between(self._boundary_ts, at),
            )
        )
        self._boundary_ts = at or self._boundary_ts
        self._carried, self._outputs = self._outputs, []
        self._tool_calls, self._text, self._thinking, self._lines = [], "", "", []

    def item_completed(self, item: dict[str, Any]) -> None:
        kind = item.get("item_type") or item.get("type") or ""
        if kind in _CODEX_TOOL_ITEMS:
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


def from_codex(log: Path, exit_code: int, workspace: Path, files_written: list[str]) -> RunResult:
    """Normalise a Codex rollout file."""
    records = read_jsonl_numbered(log)

    session_id = ""
    model = ""
    ledger = _CodexLedger()

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

    total = ledger.last_total
    reported = {k: int(v) for k, v in total.items() if isinstance(v, int | float) and not isinstance(v, bool)}

    return RunResult(
        harness="codex",
        model=model,
        session_id=session_id,
        session_log=str(log),
        workspace=str(workspace),
        exit_code=exit_code,
        duration_ms=ledger.duration_ms,
        turns=len(ledger.calls),
        final_text=ledger.final_text,
        usage=_sum(ledger.calls),
        tool_calls=ledger.tools,
        files_written=files_written,
        harness_reported_cost_usd=None,
        calls=ledger.calls,
        reported_usage=reported,
        reported_turns=ledger.tasks,
        record_kinds=record_kinds.census("codex", [rec for _, rec in records]),
        context_window=ledger.context_window,
        ttft_ms=ledger.ttft_ms,
        api_duration_ms=ledger.duration_ms or None,
    )
