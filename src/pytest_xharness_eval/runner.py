"""Drive claude / codex headlessly and capture each run's own session log.

The correlation contracts:

* Claude: the harness mints the session UUID via ``--session-id``, so the log
  path is derived before the process starts, never searched.
* Codex: no ``--session-id`` exists, so the harness points ``CODEX_HOME`` at a
  private per-run directory seeded with the credential files; exactly one
  rollout can then exist under it (ADR 0005).

The functions that spawn a CLI are excluded from coverage on purpose: this
package never mocks or fakes a CLI (ADR 0002), so they are exercised only by
paid live evals in a consuming repository.
"""

from __future__ import annotations

# Standard Library
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

# Our Libraries
from pytest_xharness_eval import normalise
from pytest_xharness_eval import workspace as ws

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Callable

    # Our Libraries
    from pytest_xharness_eval.runresult import RunResult

    Runner = Callable[..., RunResult]

DEFAULT_TIMEOUT_S = 600

# Isolation levers verified against the installed CLIs (claude 2.1.237, codex 0.148.0).
_CLAUDE_ISOLATION = ["--setting-sources", ""]
_CODEX_ISOLATION = ["--ignore-user-config", "--skip-git-repo-check"]

# Credential material Codex keeps inside CODEX_HOME (ADR 0005, risk accepted).
_CODEX_CRED_FILES = ["auth.json", ".credentials.json", "config.toml"]


class RunError(RuntimeError):
    """A cell failed in a way that must not be graded (fail loud, never degrade)."""


def _run(
    cmd: list[str], cwd: Path, env: dict[str, str], timeout_s: int
) -> subprocess.CompletedProcess[str]:  # pragma: no cover - spawns a real CLI (ADR 0002)
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout_s)


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
        *_CLAUDE_ISOLATION,
    ]
    if skill_dir is not None:
        cmd += ["--add-dir", str(skill_dir)]

    before = ws.snapshot(workspace)
    proc = _run(cmd, cwd=workspace, env=dict(os.environ), timeout_s=timeout_s)
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

    return normalise.from_claude(log, envelope, workspace, files_written=ws.diff(before, after))


def _seed_codex_home(run_dir: Path) -> Path:  # pragma: no cover - reads real credentials (ADR 0002)
    real_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    private = run_dir / "codex_home"
    private.mkdir(parents=True, exist_ok=True)
    seeded = False
    for name in _CODEX_CRED_FILES:
        src = real_home / name
        if src.is_file():
            shutil.copy2(src, private / name)
            seeded = True
    if not seeded:
        raise RunError(f"no codex credentials found under {real_home} to seed a private home")
    return private


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
    private_home = _seed_codex_home(run_dir)

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
        *_CODEX_ISOLATION,
    ]

    before = ws.snapshot(workspace)
    start = time.monotonic()
    proc = _run(cmd, cwd=workspace, env=env, timeout_s=timeout_s)
    wall_ms = int((time.monotonic() - start) * 1000)
    after = ws.snapshot(workspace)

    rollouts = sorted((private_home / "sessions").rglob("rollout-*.jsonl"))
    if len(rollouts) != 1:
        raise RunError(
            f"expected exactly one rollout under private CODEX_HOME, found {len(rollouts)}; "
            f"codex exited {proc.returncode}: {proc.stderr[:2000]}"
        )

    result = normalise.from_codex(rollouts[0], proc.returncode, workspace, files_written=ws.diff(before, after))
    if not result.duration_ms:
        result.duration_ms = wall_ms
    if not result.session_id:
        raise RunError(f"rollout {rollouts[0]} carries no session_meta id")
    return result


RUNNERS: dict[str, Runner] = {"claude": run_claude, "codex": run_codex}
