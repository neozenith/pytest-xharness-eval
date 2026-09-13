#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["lsprotocol>=2024.0.0"]
# ///
"""LSP Explorer — query language servers for code intelligence, with call edges.

FORK PROVENANCE. Lifted from .claude/skills/lsp/scripts/lsp_explorer.py on
2026-09-11 and amended, so this tree can iterate on it without editing the
skill. The original stays where it is; this is the copy the maintainability
work uses. See ../README.md for why each amendment exists.

What changed, and what each change was hiding:

1. Edges now come from callHierarchy, not semanticTokens.
   The original derived references from textDocument/semanticTokens, which
   open-source pyright does not implement (it is a Pylance feature). It
   returned empty data, the code read `if not data: return 0`, and the index
   recorded 2780 definitions and ZERO references while exiting 0. Nothing in
   the output said the call graph was empty.

2. Every document stays open for the whole index.
   The original called did_close after each file to save server memory. That
   is the openFilesOnly trap: a server asked about a position in a closed file
   answers with a plausible empty result rather than an error, so calls into
   already-indexed files silently vanish. Holding the workspace open is what
   took this repository from 0 edges to 380.

3. A missing language server is fatal.
   The original appended "LSP server not found" to a stats list and returned
   exit code 0 with files_indexed = 0. That reads as success.

4. Call sites are counted, not just distinct callers.
   callHierarchy/incomingCalls returns `fromRanges`, every call site inside the
   caller. Collapsing to one edge per (caller, callee) pair under-counts by
   about a third: 380 distinct edges against 515 call sites here. Both readings
   are stored, and the `leverage` view exposes both.

5. Anonymous lambdas are excluded.
   typescript-language-server reports every inline arrow function as a symbol
   named "map() callback". Counting those put the orphan rate on report-ui/src
   at 73%, which read as "this webapp is mostly dead code" and was an artefact.

WHAT THIS STILL CANNOT SEE, and no amendment fixes:
   dynamic dispatch (a Record<string, fn> lookup table), decorator and plugin
   registries (pluggy calls this repo's pytest hooks with no static edge), and
   anything reached by reflection. Treat the graph as a lower bound, never a
   complete picture. See ../README.md, "What we still cannot extract".

Architecture (5 layers):
    CLI (argparse)          <- User/Claude invokes commands
        |
    CodeExplorer            <- High-level: explore, plan, impact
        |
    LspSession              <- Protocol: initialize, shutdown, textDocument/*
        |
    JsonRpcClient           <- Wire: Content-Length framing, request/response matching
        |
    subprocess (stdin/stdout) <- pyright-langserver or typescript-language-server
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import re
import select
import shutil
import sqlite3
import subprocess
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

# ============================================================================
# Configuration
# ============================================================================

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()

log = logging.getLogger(__name__)

# LSP Symbol Kind mapping (from LSP spec)
SYMBOL_KIND: dict[int, str] = {
    1: "file",
    2: "module",
    3: "namespace",
    4: "package",
    5: "class",
    6: "method",
    7: "property",
    8: "field",
    9: "constructor",
    10: "enum",
    11: "interface",
    12: "function",
    13: "variable",
    14: "constant",
    15: "string",
    16: "number",
    17: "boolean",
    18: "array",
    19: "object",
    20: "key",
    21: "null",
    22: "enum_member",
    23: "struct",
    24: "event",
    25: "operator",
    26: "type_parameter",
}

# Language detection from file extensions
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
}

# Server commands per language
SERVER_COMMANDS: dict[str, list[str]] = {
    "python": ["pyright-langserver", "--stdio"],
    "typescript": ["typescript-language-server", "--stdio"],
    "javascript": ["typescript-language-server", "--stdio"],
}

# Default timeout in seconds
DEFAULT_TIMEOUT = 30.0

# Supported file extensions (reuse EXTENSION_TO_LANGUAGE keys)
SUPPORTED_EXTENSIONS = frozenset(EXTENSION_TO_LANGUAGE.keys())

# Test file classification patterns
TEST_FILE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?:^|/)tests?/"),  # test/ or tests/ directory
    re.compile(r"(?:^|/)__tests__/"),  # Jest __tests__/ convention
    re.compile(r"(?:^|/)test_[^/]+\.py$"),  # test_*.py (pytest)
    re.compile(r"(?:^|/)[^/]+_test\.py$"),  # *_test.py
    re.compile(r"(?:^|/)[^/]+\.test\.[jt]sx?$"),  # *.test.ts, *.test.tsx
    re.compile(r"(?:^|/)[^/]+\.spec\.[jt]sx?$"),  # *.spec.ts, *.spec.tsx
    re.compile(r"(?:^|/)conftest\.py$"),  # pytest conftest
    re.compile(r"(?:^|/)fixtures?/"),  # fixture/ or fixtures/ directory
]

# Semantic token types we index (skip keywords, comments, strings, numbers, operators)
INDEXABLE_TOKEN_TYPES = frozenset(
    {
        "namespace",
        "type",
        "class",
        "enum",
        "interface",
        "struct",
        "typeParameter",
        "parameter",
        "variable",
        "property",
        "enumMember",
        "function",
        "method",
    }
)

# Standard semantic token types list (LSP 3.16 spec order)
STANDARD_TOKEN_TYPES = [
    "namespace",
    "type",
    "class",
    "enum",
    "interface",
    "struct",
    "typeParameter",
    "parameter",
    "variable",
    "property",
    "enumMember",
    "event",
    "function",
    "method",
    "macro",
    "keyword",
    "modifier",
    "comment",
    "string",
    "number",
    "regexp",
    "operator",
]

# Standard semantic token modifiers list (LSP 3.16 spec order)
STANDARD_TOKEN_MODIFIERS = [
    "declaration",
    "definition",
    "readonly",
    "static",
    "deprecated",
    "abstract",
    "async",
    "modification",
    "documentation",
    "defaultLibrary",
]

# Cache configuration
CACHE_DIR = Path.cwd() / ".claude" / "cache"
CACHE_DB_PATH = CACHE_DIR / "lsp_index.db"
INDEX_SCHEMA_VERSION = "1"

# SQL schema for the symbol index
INDEX_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS cache_metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS source_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath TEXT UNIQUE NOT NULL,
    relative_path TEXT NOT NULL,
    mtime REAL NOT NULL,
    size_bytes INTEGER NOT NULL,
    indexed_at TEXT NOT NULL,
    language TEXT NOT NULL,
    lsp_server TEXT NOT NULL,
    file_type TEXT NOT NULL CHECK (file_type IN ('source', 'test'))
);

CREATE TABLE IF NOT EXISTS symbols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file_id INTEGER NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    line INTEGER NOT NULL,
    col INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    end_col INTEGER NOT NULL,
    detail TEXT,
    is_definition BOOLEAN NOT NULL DEFAULT 0,
    scope_start_line INTEGER,
    scope_end_line INTEGER,
    UNIQUE(source_file_id, name, line, col)
);

CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_source_file ON symbols(source_file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_definition ON symbols(is_definition) WHERE is_definition = 1;

CREATE VIEW IF NOT EXISTS definitions AS
SELECT * FROM symbols WHERE is_definition = 1;

CREATE VIEW IF NOT EXISTS "references" AS
SELECT * FROM symbols WHERE is_definition = 0;

CREATE TABLE IF NOT EXISTS symbol_containments (
    inner_symbol_id INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    outer_symbol_id INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    PRIMARY KEY (inner_symbol_id, outer_symbol_id)
);
CREATE INDEX IF NOT EXISTS idx_containments_outer ON symbol_containments(outer_symbol_id);
CREATE INDEX IF NOT EXISTS idx_containments_inner ON symbol_containments(inner_symbol_id);

-- Call edges from callHierarchy. One row per (caller, callee) definition pair.
-- `sites` is how many call sites inside the caller reach the callee, so a
-- consumer can count rows for distinct callers or sum `sites` for call sites.
-- These two readings differ by about a third on a real codebase.
CREATE TABLE IF NOT EXISTS call_edges (
    caller_symbol_id INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    callee_symbol_id INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    sites INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (caller_symbol_id, callee_symbol_id)
);
CREATE INDEX IF NOT EXISTS idx_call_edges_callee ON call_edges(callee_symbol_id);

-- Leverage: distinct callers and total call sites per definition. The metric
-- README.md calls "how many sites does this one name save you from reading".
CREATE VIEW IF NOT EXISTS leverage AS
SELECT s.id AS symbol_id, s.name, sf.relative_path, s.line,
       COUNT(e.caller_symbol_id) AS callers,
       COALESCE(SUM(e.sites), 0)  AS call_sites
  FROM symbols s
  JOIN source_files sf ON sf.id = s.source_file_id
  LEFT JOIN call_edges e ON e.callee_symbol_id = s.id
 WHERE s.is_definition = 1
 GROUP BY s.id;
"""

# R-Tree schema (separate because it needs its own availability check)
RTREE_SCHEMA_SQL = """\
CREATE VIRTUAL TABLE IF NOT EXISTS definition_ranges USING rtree(
    id,
    min_line, max_line,
    min_file_id, max_file_id
);
"""


# ============================================================================
# Layer 1: JSON-RPC Client
# ============================================================================


class JsonRpcError(Exception):
    """Error from a JSON-RPC response."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(f"JSON-RPC error {code}: {message}")
        self.code = code
        self.error_message = message
        self.data = data


class JsonRpcClient:
    """Low-level JSON-RPC 2.0 client over stdio with Content-Length framing.

    The LSP wire protocol uses HTTP-style Content-Length headers to delimit
    JSON messages over stdin/stdout of a subprocess. Each message looks like:

        Content-Length: 52\\r\\n
        \\r\\n
        {"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}

    Architecture: Single-threaded IO with our own byte buffer and raw fd reads.
    We bypass Python's BufferedReader entirely because its internal buffer is
    invisible to select.select() — after one readline() call, BufferedReader
    may greedily consume multiple messages into its buffer, but select() on the
    raw fd reports "no data" because the fd was drained. This causes timeouts
    when the buffered messages are never read.

    Instead, we use os.read() on the raw fd + select.select() for timeouts,
    maintaining our own _buffer (bytearray). This gives us full control over
    both timeout detection and data buffering. Server-initiated requests are
    handled inline during wait_response() to prevent deadlocks.
    """

    def __init__(self, proc: subprocess.Popen[bytes]) -> None:
        self._proc = proc
        self._next_id = 1
        self._pending_notifications: list[dict[str, Any]] = []
        assert proc.stdin is not None
        assert proc.stdout is not None
        self._stdin = proc.stdin
        self._stdout_fd = proc.stdout.fileno()
        # Our own buffer — replaces Python's BufferedReader
        self._buffer = bytearray()

    def send_request(self, method: str, params: dict[str, Any] | None = None) -> int:
        """Send a JSON-RPC request and return the request ID."""
        request_id = self._next_id
        self._next_id += 1
        msg: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            msg["params"] = params
        self._send(msg)
        log.debug("-> request id=%d method=%s", request_id, method)
        return request_id

    def send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        msg: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            msg["params"] = params
        self._send(msg)
        log.debug("-> notification method=%s", method)

    def wait_response(self, request_id: int, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
        """Read messages until we get a response for our request_id.

        Three message types are handled:
        1. Responses (id + result/error) — matched to our request by id
        2. Server requests (id + method) — auto-responded to prevent deadlocks
        3. Notifications (method only) — buffered for later collection

        Uses select.select() on the raw fd for timeout, then buffered reads
        for efficient message parsing.
        """
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"No response for request {request_id} within {timeout}s")

            msg = self._read_one_message(remaining)
            if msg is None:
                raise TimeoutError(f"No response for request {request_id} within {timeout}s")

            has_id = "id" in msg
            has_method = "method" in msg

            if has_id and has_method:
                # Server request — respond immediately to prevent deadlocks
                self._handle_server_request(msg)
            elif has_id and not has_method:
                # Response
                if msg["id"] == request_id:
                    if "error" in msg:
                        err = msg["error"]
                        raise JsonRpcError(
                            err.get("code", -1),
                            err.get("message", "Unknown"),
                            err.get("data"),
                        )
                    log.debug("<- response id=%d", request_id)
                    result: dict[str, Any] = msg["result"]
                    return result
                else:
                    log.warning(
                        "Received response for unexpected id=%s",
                        msg["id"],
                    )
            else:
                # Notification — buffer for later
                self._pending_notifications.append(msg)
                log.debug("<- notification method=%s", msg.get("method", "?"))

    def _handle_server_request(self, msg: dict[str, Any]) -> None:
        """Respond to server-initiated requests.

        LSP servers can send requests to the client (e.g., workspace/configuration,
        client/registerCapability). If we don't respond, the server blocks waiting
        and never processes our requests — causing timeouts.
        """
        method = msg.get("method", "")
        req_id = msg["id"]
        log.debug("<- server request id=%s method=%s", req_id, method)

        if method == "workspace/configuration":
            items = msg.get("params", {}).get("items", [])
            response: dict[str, Any] = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": [{}] * len(items),
            }
            self._send(response)
            log.debug(
                "-> response to workspace/configuration (%d items)",
                len(items),
            )
        elif method == "client/registerCapability":
            response = {"jsonrpc": "2.0", "id": req_id, "result": None}
            self._send(response)
            log.debug("-> response to client/registerCapability")
        elif method == "window/workDoneProgress/create":
            response = {"jsonrpc": "2.0", "id": req_id, "result": None}
            self._send(response)
            log.debug("-> response to window/workDoneProgress/create")
        else:
            response = {"jsonrpc": "2.0", "id": req_id, "result": None}
            self._send(response)
            log.debug("-> response to %s (generic null)", method)

    def drain_notifications(self, timeout: float = 0.5) -> list[dict[str, Any]]:
        """Collect all pending + incoming notifications.

        Reads messages for up to `timeout` seconds, handling server requests
        and buffering notifications. Useful for collecting diagnostics.
        """
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            msg = self._read_one_message(remaining)
            if msg is None:
                break
            has_id = "id" in msg
            has_method = "method" in msg
            if has_id and has_method:
                self._handle_server_request(msg)
            elif has_id and not has_method:
                log.warning("Unexpected response while draining: %s", msg)
            else:
                self._pending_notifications.append(msg)

        result = self._pending_notifications[:]
        self._pending_notifications.clear()
        return result

    def _send(self, msg: dict[str, Any]) -> None:
        """Encode and send a JSON-RPC message with Content-Length header."""
        body = json.dumps(msg).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        self._stdin.write(header + body)
        self._stdin.flush()

    def _fill_buffer(self, timeout: float) -> bool:
        """Read more data from the fd into our buffer.

        Returns True if new data was read, False on timeout or EOF.
        Uses select.select() for timeout, then os.read() for data.
        Always attempts to read from the fd, even if buffer has data.
        """
        ready, _, _ = select.select([self._stdout_fd], [], [], timeout)
        if not ready:
            return False
        chunk = os.read(self._stdout_fd, 65536)
        if not chunk:
            return False  # EOF
        self._buffer.extend(chunk)
        return True

    def _read_line_raw(self, timeout: float) -> bytes | None:
        """Read one line (ending in \\n) from our buffer + fd.

        Returns the line including the trailing \\n, or None on timeout/EOF.
        """
        deadline = time.monotonic() + timeout
        while True:
            # Check if we already have a complete line in the buffer
            newline_pos = self._buffer.find(b"\n")
            if newline_pos >= 0:
                line = bytes(self._buffer[: newline_pos + 1])
                del self._buffer[: newline_pos + 1]
                return line
            # Need more data
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            if not self._fill_buffer(remaining):
                return None

    def _read_exactly_raw(self, n: int, timeout: float) -> bytes | None:
        """Read exactly n bytes from our buffer + fd.

        Returns exactly n bytes, or None on timeout/EOF.
        """
        deadline = time.monotonic() + timeout
        while len(self._buffer) < n:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            if not self._fill_buffer(remaining):
                return None
        data = bytes(self._buffer[:n])
        del self._buffer[:n]
        return data

    def _read_one_message(self, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any] | None:
        """Read a single Content-Length-framed JSON-RPC message.

        Uses our own buffer + raw os.read() on the fd, with select.select()
        for timeout detection. This avoids the classic BufferedReader pitfall
        where Python's internal buffer holds data invisible to select().

        Protocol format:
            Content-Length: <n>\\r\\n
            \\r\\n
            <n bytes of JSON body>
        """
        deadline = time.monotonic() + timeout

        # Read headers until empty line
        headers: list[str] = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            line = self._read_line_raw(remaining)
            if line is None:
                return None
            line_str = line.decode("ascii").rstrip("\r\n")
            if line_str == "":
                break
            headers.append(line_str)

        # Parse Content-Length
        content_length = 0
        for header_line in headers:
            if header_line.lower().startswith("content-length:"):
                content_length = int(header_line.split(":", 1)[1].strip())

        if content_length == 0:
            log.warning("No Content-Length in headers: %s", headers)
            return None

        # Read body
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        body = self._read_exactly_raw(content_length, remaining)
        if body is None or len(body) < content_length:
            return None

        return json.loads(body.decode("utf-8"))  # type: ignore[no-any-return]


# ============================================================================
# Layer 2: LSP Session
# ============================================================================


def _file_uri(path: Path) -> str:
    """Convert a file path to a file:// URI."""
    return path.resolve().as_uri()


def _read_file_text(path: Path) -> str:
    """Read file contents for didOpen notification."""
    return path.read_text(encoding="utf-8", errors="replace")


# typescript-language-server reports every inline arrow function as a symbol
# named "map() callback", "filter() callback" and so on. They are not names:
# nobody learns them and nothing calls them by name. Counting them put the
# orphan rate on report-ui/src at 73%, which read as "this webapp is mostly
# dead code" and was entirely an artefact.
ANONYMOUS_SYMBOL = re.compile(r"\(\) callback$|^<anonymous>$|^\(\)")


def _caller_location(item: dict[str, Any]) -> tuple[str, int] | None:
    """Map a callHierarchy item onto (absolute path, 1-indexed line).

    Absolute, deliberately. source_files stores both `filepath` (absolute) and
    `relative_path` (git-relative), and the latter only coincides with a path
    made relative to the *indexing root* when that root is the repo root.
    Matching on the absolute path works for any --root.
    """
    uri = item.get("uri", "")
    if not uri.startswith("file://"):
        return None
    rng = item.get("selectionRange") or item.get("range") or {}
    line = (rng.get("start") or {}).get("line")
    if line is None:
        return None
    return (str(Path(uri[7:]).resolve()), line + 1)


class LspSession:
    """LSP protocol operations wrapping a JsonRpcClient.

    Handles the LSP lifecycle (initialize/shutdown) and provides
    typed wrappers for common textDocument/* requests.

    LSP positions are 0-indexed (line 0, character 0 = first character).
    This class works in 0-indexed coordinates internally.
    """

    def __init__(self, client: JsonRpcClient, root_path: Path, language: str) -> None:
        self._client = client
        self._root_path = root_path
        self._language = language
        self._open_docs: set[str] = set()
        self._initialized = False
        self._semantic_tokens_legend: dict[str, Any] | None = None

    @property
    def language(self) -> str:
        return self._language

    def initialize(self) -> dict[str, Any]:
        """Perform the LSP 3-way handshake: initialize -> response -> initialized.

        The initialize request tells the server about client capabilities and
        the project root. The server responds with its own capabilities.
        Then we send an 'initialized' notification to complete the handshake.
        """
        params = {
            "processId": os.getpid(),
            "rootUri": _file_uri(self._root_path),
            "rootPath": str(self._root_path),
            "capabilities": {
                "textDocument": {
                    "documentSymbol": {
                        "hierarchicalDocumentSymbolSupport": True,
                    },
                    "definition": {"linkSupport": False},
                    "references": {},
                    "hover": {"contentFormat": ["plaintext", "markdown"]},
                    "publishDiagnostics": {"relatedInformation": True},
                    "semanticTokens": {
                        "requests": {"full": True},
                        "tokenTypes": STANDARD_TOKEN_TYPES,
                        "tokenModifiers": STANDARD_TOKEN_MODIFIERS,
                        "formats": ["relative"],
                    },
                },
                # Note: we intentionally do NOT advertise workspace.workspaceFolders
                # capability. Pyright deadlocks when this is set — it blocks internally
                # waiting for workspace/configuration negotiation that never completes.
                # Workspace folders are still provided via params.workspaceFolders above.
            },
            "workspaceFolders": [{"uri": _file_uri(self._root_path), "name": self._root_path.name}],
        }
        req_id = self._client.send_request("initialize", params)
        result = self._client.wait_response(req_id)

        # Capture semantic tokens legend from server capabilities
        caps = result.get("capabilities", {})
        st_provider = caps.get("semanticTokensProvider", {})
        self._semantic_tokens_legend = st_provider.get("legend")

        # Complete the handshake
        self._client.send_notification("initialized", {})

        # Drain post-initialization messages (window/logMessage, etc.)
        # and respond to any server requests (client/registerCapability).
        self._client.drain_notifications(timeout=0.5)

        self._initialized = True
        log.info("LSP initialized for %s at %s", self._language, self._root_path)
        return result

    def shutdown(self) -> None:
        """Gracefully shut down the LSP session."""
        # Close any open documents first
        for uri in list(self._open_docs):
            self._client.send_notification(
                "textDocument/didClose",
                {"textDocument": {"uri": uri}},
            )
        self._open_docs.clear()

        req_id = self._client.send_request("shutdown")
        try:
            self._client.wait_response(req_id, timeout=5.0)
        except (TimeoutError, JsonRpcError):
            log.warning("Shutdown response not received cleanly")
        self._client.send_notification("exit")
        self._initialized = False
        log.info("LSP session shut down")

    def did_open(self, file_path: Path) -> None:
        """Open a document in the language server.

        The LSP requires documents to be "opened" before querying them.
        We send the full file contents as part of the didOpen notification.
        """
        uri = _file_uri(file_path)
        if uri in self._open_docs:
            return
        lang_id = self._language
        if lang_id == "javascript":
            lang_id = "javascriptreact" if file_path.suffix == ".jsx" else "javascript"
        elif lang_id == "typescript":
            lang_id = "typescriptreact" if file_path.suffix == ".tsx" else "typescript"

        text = _read_file_text(file_path)
        self._client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": lang_id,
                    "version": 1,
                    "text": text,
                },
            },
        )
        self._open_docs.add(uri)
        log.debug("Opened document: %s", file_path)

    def did_close(self, file_path: Path) -> None:
        """Close a document in the language server."""
        uri = _file_uri(file_path)
        if uri not in self._open_docs:
            return
        self._client.send_notification(
            "textDocument/didClose",
            {"textDocument": {"uri": uri}},
        )
        self._open_docs.discard(uri)

    def document_symbol(self, file_path: Path) -> list[dict[str, Any]]:
        """Get symbols in a document (textDocument/documentSymbol).

        Returns hierarchical symbols (DocumentSymbol[]) if the server supports it,
        otherwise flat SymbolInformation[].
        """
        self.did_open(file_path)
        uri = _file_uri(file_path)
        req_id = self._client.send_request(
            "textDocument/documentSymbol",
            {"textDocument": {"uri": uri}},
        )
        result = self._client.wait_response(req_id)
        return result if isinstance(result, list) else []

    def definition(self, file_path: Path, line: int, col: int) -> list[dict[str, Any]]:
        """Go to definition (textDocument/definition).

        Args:
            file_path: File containing the symbol
            line: 0-indexed line number
            col: 0-indexed column number
        """
        self.did_open(file_path)
        uri = _file_uri(file_path)
        req_id = self._client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": col},
            },
        )
        result = self._client.wait_response(req_id)
        if result is None:
            return []
        if isinstance(result, dict):
            return [result]
        return result if isinstance(result, list) else []

    def references(self, file_path: Path, line: int, col: int) -> list[dict[str, Any]]:
        """Find all references (textDocument/references).

        Args:
            file_path: File containing the symbol
            line: 0-indexed line number
            col: 0-indexed column number
        """
        self.did_open(file_path)
        uri = _file_uri(file_path)
        req_id = self._client.send_request(
            "textDocument/references",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": col},
                "context": {"includeDeclaration": True},
            },
        )
        result = self._client.wait_response(req_id)
        if result is None:
            return []
        return result if isinstance(result, list) else []

    def hover(self, file_path: Path, line: int, col: int) -> dict[str, Any] | None:
        """Get hover information (textDocument/hover).

        Args:
            file_path: File containing the symbol
            line: 0-indexed line number
            col: 0-indexed column number
        """
        self.did_open(file_path)
        uri = _file_uri(file_path)
        req_id = self._client.send_request(
            "textDocument/hover",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": col},
            },
        )
        result = self._client.wait_response(req_id)
        return result if isinstance(result, dict) else None

    def collect_diagnostics(self, file_path: Path, timeout: float = 3.0) -> list[dict[str, Any]]:
        """Collect publishDiagnostics notifications for a file.

        After opening a document, the server asynchronously sends diagnostics
        as notifications. This method drains the notification buffer and
        returns diagnostics for the specified file.
        """
        self.did_open(file_path)
        uri = _file_uri(file_path)

        notifications = self._client.drain_notifications(timeout=timeout)
        diagnostics: list[dict[str, Any]] = []
        for notif in notifications:
            if notif.get("method") == "textDocument/publishDiagnostics":
                params = notif.get("params", {})
                if params.get("uri") == uri:
                    diagnostics.extend(params.get("diagnostics", []))
        return diagnostics

    def semantic_tokens(self, file_path: Path) -> dict[str, Any]:
        """Get all semantic tokens for a document (textDocument/semanticTokens/full)."""
        self.did_open(file_path)
        uri = _file_uri(file_path)
        req_id = self._client.send_request(
            "textDocument/semanticTokens/full",
            {"textDocument": {"uri": uri}},
        )
        return self._client.wait_response(req_id) or {}

    @property
    def semantic_tokens_legend(self) -> dict[str, Any] | None:
        """The semantic tokens legend from the server's capabilities."""
        return self._semantic_tokens_legend

    # -- call hierarchy ------------------------------------------------------
    #
    # The two requests this fork exists for. The original derived references
    # from semanticTokens, which open-source pyright does not implement (it is
    # a Pylance feature), so the index recorded zero references and the failure
    # was silent. These are implemented by both pyright and
    # typescript-language-server, and they return *calls* rather than tokens
    # that happen to share a name.

    def prepare_call_hierarchy(self, file_path: Path, line: int, col: int) -> list[dict[str, Any]]:
        """textDocument/prepareCallHierarchy at a 1-indexed position."""
        self.did_open(file_path)
        req_id = self._client.send_request(
            "textDocument/prepareCallHierarchy",
            {
                "textDocument": {"uri": _file_uri(file_path)},
                "position": {"line": line - 1, "character": col - 1},
            },
        )
        result = self._client.wait_response(req_id)
        return result if isinstance(result, list) else []

    def incoming_calls(self, item: dict[str, Any]) -> list[tuple[dict[str, Any], int]]:
        """callHierarchy/incomingCalls. Returns (caller item, call site count).

        `fromRanges` lists EVERY call site inside that caller, not just one, so
        a caller that calls the target four times yields one item with four
        ranges. Collapsing to a set of (caller, callee) pairs measures distinct
        calling functions rather than call sites, which under-counts by about a
        third on this repository. The count is returned so the caller can choose.
        """
        req_id = self._client.send_request("callHierarchy/incomingCalls", {"item": item})
        result = self._client.wait_response(req_id)
        if not isinstance(result, list):
            return []
        return [(c["from"], len(c.get("fromRanges") or [1])) for c in result if "from" in c]


# ============================================================================
# Layer 3: Language Server Manager
# ============================================================================


class ServerNotFound(Exception):
    """Raised when a language server binary is not found."""

    def __init__(self, language: str, binary: str) -> None:
        self.language = language
        self.binary = binary
        install_hint = (
            "pip install pyright" if language == "python" else "npm install -g typescript-language-server typescript"
        )
        super().__init__(f"Language server for {language} not found: {binary}. Install with: {install_hint}")


class UnsupportedLanguage(Exception):
    """Raised for file types we don't support."""

    def __init__(self, ext: str) -> None:
        self.ext = ext
        super().__init__(
            f"Unsupported file extension: {ext}. Supported: {', '.join(sorted(EXTENSION_TO_LANGUAGE.keys()))}"
        )


def detect_language(file_path: Path) -> str:
    """Detect language from file extension."""
    ext = file_path.suffix.lower()
    lang = EXTENSION_TO_LANGUAGE.get(ext)
    if lang is None:
        raise UnsupportedLanguage(ext)
    return lang


def detect_project_root(file_path: Path) -> Path:
    """Walk up from file_path to find the project root.

    Looks for common project markers: .git, pyproject.toml, package.json, etc.
    Falls back to file's parent directory.
    """
    markers = {".git", "pyproject.toml", "package.json", "tsconfig.json", "setup.py", "Cargo.toml"}
    current = file_path.resolve().parent
    while current != current.parent:
        if any((current / m).exists() for m in markers):
            return current
        current = current.parent
    return file_path.resolve().parent


class LanguageServerManager:
    """Manages the lifecycle of a language server subprocess.

    Handles:
    - Language detection from file extension
    - Binary validation (is pyright-langserver on PATH?)
    - Subprocess creation (stdin/stdout pipes)
    - Creating JsonRpcClient + LspSession
    - Clean shutdown
    """

    def __init__(self, language: str) -> None:
        self._language = language
        self._proc: subprocess.Popen[bytes] | None = None
        self._session: LspSession | None = None

    @classmethod
    def for_file(cls, file_path: Path) -> LanguageServerManager:
        """Create a manager for the given file's language."""
        lang = detect_language(file_path)
        return cls(lang)

    def start(self, root_path: Path) -> LspSession:
        """Start the language server and perform initialization."""
        cmd = SERVER_COMMANDS.get(self._language)
        if cmd is None:
            raise UnsupportedLanguage(f"No server configured for {self._language}")

        binary = cmd[0]
        if shutil.which(binary) is None:
            raise ServerNotFound(self._language, binary)

        log.info("Starting %s: %s", self._language, " ".join(cmd))
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(root_path),
        )
        client = JsonRpcClient(self._proc)
        self._session = LspSession(client, root_path, self._language)
        self._session.initialize()
        return self._session

    def stop(self) -> None:
        """Shut down the language server."""
        if self._session is not None:
            try:
                self._session.shutdown()
            except Exception:
                log.warning("Error during LSP shutdown", exc_info=True)
            self._session = None

        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()
            self._proc = None

    @contextmanager
    def lsp_session(self, root_path: Path) -> Generator[LspSession, None, None]:
        """Context manager for a complete LSP session lifecycle."""
        session = self.start(root_path)
        try:
            yield session
        finally:
            self.stop()


@contextmanager
def lsp_session_for_file(file_path: Path, root_path: Path | None = None) -> Generator[LspSession, None, None]:
    """Convenience context manager: detect language, start server, yield session."""
    resolved = file_path.resolve()
    if root_path is None:
        root_path = detect_project_root(resolved)
    mgr = LanguageServerManager.for_file(resolved)
    with mgr.lsp_session(root_path) as session:
        yield session


# ============================================================================
# Layer 4: Code Explorer
# ============================================================================


def _relative_path(path: Path, root: Path) -> str:
    """Get relative path string from root, or absolute if outside root."""
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def _uri_to_path(uri: str) -> Path:
    """Convert file:// URI to Path."""
    if uri.startswith("file://"):
        # Handle file:///path and file://host/path
        parsed = urlparse(uri)
        return Path(unquote(parsed.path))
    return Path(uri)


def _symbol_kind_name(kind_num: int) -> str:
    """Get human-readable symbol kind name."""
    return SYMBOL_KIND.get(kind_num, f"unknown({kind_num})")


def _format_symbol(sym: dict[str, Any]) -> dict[str, Any]:
    """Convert an LSP DocumentSymbol to compact JSON format.

    Compact keys: n=name, k=kind, r=range[start,end], ch=children
    Lines are 1-indexed in output (LSP uses 0-indexed).
    """
    result: dict[str, Any] = {
        "n": sym.get("name", ""),
        "k": _symbol_kind_name(sym.get("kind", 0)),
    }

    # Range: convert 0-indexed to 1-indexed
    rng = sym.get("range") or sym.get("location", {}).get("range")
    if rng:
        start_line = rng["start"]["line"] + 1
        end_line = rng["end"]["line"] + 1
        result["r"] = [start_line, end_line]

    # Selection range (where the symbol name is)
    sel = sym.get("selectionRange")
    if sel:
        result["l"] = sel["start"]["line"] + 1
        result["c"] = sel["start"]["character"] + 1

    # Recursively format children
    children = sym.get("children", [])
    if children:
        result["ch"] = [_format_symbol(c) for c in children]

    # Detail (type annotation etc.)
    detail = sym.get("detail")
    if detail:
        result["d"] = detail

    return result


def _format_location(loc: dict[str, Any], root: Path) -> dict[str, Any]:
    """Convert an LSP Location to compact format."""
    result: dict[str, Any] = {}
    uri = loc.get("uri", loc.get("targetUri", ""))
    if uri:
        result["f"] = _relative_path(_uri_to_path(uri), root)

    rng = loc.get("range", loc.get("targetRange"))
    if rng:
        result["l"] = rng["start"]["line"] + 1
        result["c"] = rng["start"]["character"] + 1

    return result


def _get_line_preview(file_path: Path, line_1indexed: int) -> str | None:
    """Read a specific line from a file (1-indexed)."""
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        idx = line_1indexed - 1
        if 0 <= idx < len(lines):
            return lines[idx].rstrip()
    except OSError:
        pass
    return None


def _format_hover(result: dict[str, Any] | None) -> dict[str, Any] | None:
    """Convert LSP hover result to compact format."""
    if result is None:
        return None
    contents = result.get("contents")
    if contents is None:
        return None

    # MarkupContent: {"kind": "markdown"|"plaintext", "value": "..."}
    if isinstance(contents, dict):
        text = contents.get("value", "")
    elif isinstance(contents, str):
        text = contents
    elif isinstance(contents, list):
        # Array of MarkedString
        parts = []
        for item in contents:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("value", ""))
        text = "\n".join(parts)
    else:
        return None

    if not text.strip():
        return None

    out: dict[str, Any] = {}
    # Try to separate type signature from documentation
    lines = text.strip().split("\n")
    # If it looks like a code block, extract the signature
    if lines and lines[0].startswith("```"):
        # Find end of code block
        end_idx = 1
        for i in range(1, len(lines)):
            if lines[i].startswith("```"):
                end_idx = i
                break
        sig = "\n".join(lines[1:end_idx]).strip()
        doc_lines = lines[end_idx + 1 :]
        if sig:
            out["type"] = sig
        doc = "\n".join(doc_lines).strip()
        # Remove horizontal rule separators (common in LSP hover markdown)
        while doc.startswith("---"):
            doc = doc[3:].strip()
        while doc.endswith("---"):
            doc = doc[:-3].strip()
        if doc:
            out["doc"] = doc
    else:
        out["type"] = text.strip()

    return out if out else None


def _format_diagnostic(diag: dict[str, Any], file_path: Path, root: Path) -> dict[str, Any]:
    """Convert LSP Diagnostic to compact format."""
    result: dict[str, Any] = {"f": _relative_path(file_path, root)}
    rng = diag.get("range", {})
    start = rng.get("start", {})
    result["l"] = start.get("line", 0) + 1
    result["c"] = start.get("character", 0) + 1
    result["s"] = diag.get("severity", 1)  # 1=error, 2=warning, 3=info, 4=hint
    result["msg"] = diag.get("message", "")
    source = diag.get("source")
    if source:
        result["src"] = source
    code = diag.get("code")
    if code is not None:
        result["code"] = code
    return result


class CodeExplorer:
    """High-level code exploration operations.

    Each method opens a short-lived LSP session, performs queries,
    and returns token-efficient JSON-ready dicts.
    """

    def __init__(self, root_path: Path | None = None, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._root_override = root_path
        self._timeout = timeout

    def _root_for(self, file_path: Path) -> Path:
        if self._root_override:
            return self._root_override
        return detect_project_root(file_path)

    def symbols(self, file_path: Path) -> list[dict[str, Any]]:
        """List symbols in a file with hierarchy."""
        resolved = file_path.resolve()
        root = self._root_for(resolved)
        with lsp_session_for_file(resolved, root) as session:
            raw_symbols = session.document_symbol(resolved)
        return [_format_symbol(s) for s in raw_symbols]

    def definition(self, file_path: Path, line: int, col: int) -> list[dict[str, Any]]:
        """Go to definition. Positions are 1-indexed (converted internally)."""
        resolved = file_path.resolve()
        root = self._root_for(resolved)
        with lsp_session_for_file(resolved, root) as session:
            raw = session.definition(resolved, line - 1, col - 1)

        results = []
        for loc in raw:
            formatted = _format_location(loc, root)
            # Add source preview
            if "f" in formatted and "l" in formatted:
                target = root / formatted["f"]
                preview = _get_line_preview(target, formatted["l"])
                if preview:
                    formatted["preview"] = preview
            results.append(formatted)
        return results

    def references(self, file_path: Path, line: int, col: int) -> dict[str, Any]:
        """Find all references. Positions are 1-indexed. Returns grouped by file."""
        resolved = file_path.resolve()
        root = self._root_for(resolved)
        with lsp_session_for_file(resolved, root) as session:
            raw = session.references(resolved, line - 1, col - 1)

        # Group by file
        by_file: dict[str, list[int]] = {}
        for loc in raw:
            formatted = _format_location(loc, root)
            f = formatted.get("f", "?")
            line_num = formatted.get("l", 0)
            if f not in by_file:
                by_file[f] = []
            by_file[f].append(line_num)

        return {"refs": by_file, "total": len(raw)}

    def hover(self, file_path: Path, line: int, col: int) -> dict[str, Any] | None:
        """Get hover info. Positions are 1-indexed."""
        resolved = file_path.resolve()
        root = self._root_for(resolved)
        with lsp_session_for_file(resolved, root) as session:
            raw = session.hover(resolved, line - 1, col - 1)
        return _format_hover(raw)

    def diagnostics(self, file_path: Path) -> list[dict[str, Any]]:
        """Get diagnostics for a file."""
        resolved = file_path.resolve()
        root = self._root_for(resolved)
        with lsp_session_for_file(resolved, root) as session:
            raw = session.collect_diagnostics(resolved, timeout=self._timeout)
        return [_format_diagnostic(d, resolved, root) for d in raw]

    def explore(self, file_path: Path) -> dict[str, Any]:
        """Combined symbols + diagnostics overview for a file."""
        resolved = file_path.resolve()
        root = self._root_for(resolved)
        lang = detect_language(resolved)
        with lsp_session_for_file(resolved, root) as session:
            raw_symbols = session.document_symbol(resolved)
            raw_diags = session.collect_diagnostics(resolved, timeout=min(self._timeout, 5.0))

        syms = [_format_symbol(s) for s in raw_symbols]
        diags = [_format_diagnostic(d, resolved, root) for d in raw_diags]

        result: dict[str, Any] = {
            "file": _relative_path(resolved, root),
            "lang": lang,
            "symbols": len(syms),
            "diagnostics": len(diags),
            "syms": syms,
        }
        if diags:
            result["diags"] = diags
        return result

    def impact(self, file_path: Path, line: int, col: int, depth: int = 1) -> dict[str, Any]:
        """Multi-hop reference analysis. Find what a change would affect.

        Traces references up to `depth` hops from the starting symbol.
        Positions are 1-indexed.
        """
        resolved = file_path.resolve()
        root = self._root_for(resolved)
        refs_result = self.references(file_path, line, col)

        # For depth > 1, we'd recursively trace references of each reference.
        # For now, depth=1 returns direct references.
        affected: list[dict[str, Any]] = []
        for f, lines in refs_result.get("refs", {}).items():
            for ln in lines:
                entry: dict[str, Any] = {"f": f, "l": ln}
                preview = _get_line_preview(root / f, ln)
                if preview:
                    entry["preview"] = preview
                affected.append(entry)

        return {
            "depth": depth,
            "total": refs_result.get("total", 0),
            "affected": affected,
        }


# ============================================================================
# Layer 5: Symbol Index Cache (SQLite)
# ============================================================================


def classify_file_type(relative_path: str) -> str:
    """Classify a file as 'test' or 'source' based on path patterns."""
    for pattern in TEST_FILE_PATTERNS:
        if pattern.search(relative_path):
            return "test"
    return "source"


def decode_semantic_tokens(
    data: list[int],
    legend: dict[str, Any],
    source_text: str,
) -> list[dict[str, Any]]:
    """Decode a delta-encoded semantic tokens array into token records.

    The data array encodes tokens as groups of 5 integers:
    [deltaLine, deltaStartChar, length, tokenTypeIndex, tokenModifiersBitmask]

    Positions are relative to the previous token (first relative to 0,0).
    """
    token_types = legend.get("tokenTypes", STANDARD_TOKEN_TYPES)
    token_modifiers = legend.get("tokenModifiers", STANDARD_TOKEN_MODIFIERS)

    # Find declaration/definition modifier bit positions
    decl_bit = token_modifiers.index("declaration") if "declaration" in token_modifiers else -1
    defn_bit = token_modifiers.index("definition") if "definition" in token_modifiers else -1

    source_lines = source_text.splitlines()
    tokens: list[dict[str, Any]] = []

    line = 0
    col = 0

    for i in range(0, len(data) - 4, 5):
        delta_line = data[i]
        delta_start_char = data[i + 1]
        length = data[i + 2]
        type_idx = data[i + 3]
        mod_bits = data[i + 4]

        # Advance position
        if delta_line > 0:
            line += delta_line
            col = delta_start_char
        else:
            col += delta_start_char

        # Get token type name
        if type_idx >= len(token_types):
            continue
        token_type = token_types[type_idx]

        # Skip non-indexable types
        if token_type not in INDEXABLE_TOKEN_TYPES:
            continue

        # Determine if this is a definition site
        is_def = False
        if decl_bit >= 0 and (mod_bits & (1 << decl_bit)):
            is_def = True
        if defn_bit >= 0 and (mod_bits & (1 << defn_bit)):
            is_def = True

        # Extract name from source text
        name = ""
        if 0 <= line < len(source_lines):
            src_line = source_lines[line]
            if col < len(src_line):
                name = src_line[col : col + length]

        if not name:
            continue

        tokens.append(
            {
                "name": name,
                "kind": token_type,
                "line": line + 1,  # 1-indexed
                "col": col + 1,  # 1-indexed
                "end_line": line + 1,
                "end_col": col + length + 1,
                "is_definition": is_def,
            }
        )

    return tokens


class IndexCacheManager:
    """SQLite-backed symbol index for pre-computed definitions and references.

    Stores all symbols (definitions + references) in a single `symbols` table.
    Definitions are marked with `is_definition=1` and have scope ranges.
    References are `is_definition=0`. Both are exposed as SQL VIEWs.

    Definition scope ranges are indexed in an R-Tree virtual table for
    O(log N) interval containment queries. A materialized `symbol_containments`
    edge list captures the nesting structure for graph traversal CTEs.
    """

    def __init__(self, db_path: Path = CACHE_DB_PATH, edge_source: str = "callhierarchy") -> None:
        # "callhierarchy" writes real call edges and is the default. "tokens"
        # keeps the original semanticTokens path, which pyright does not
        # implement and which therefore yields nothing on a Python workspace.
        self.edge_source = edge_source
        # The LSP workspace root, when it differs from the directory being walked.
        # --root serves double duty in the original: it picks which files to index
        # AND which directory the server is initialised on. Pointing pyright at a
        # package subdirectory with no pyproject.toml degrades its import
        # resolution and silently halves the edge count (189 against 380 here).
        # typescript-language-server refuses to start at all, because it resolves
        # tsserver from the workspace root.
        self.lsp_root: Path | None = None
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Lazy connection with foreign keys enabled."""
        if self._conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def init_schema(self) -> None:
        """Create tables, views, and indexes. Fail-fast if R-Tree unavailable."""
        # Check R-Tree availability
        try:
            self.conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _rtree_check USING rtree(id, x1, x2)")
            self.conn.execute("DROP TABLE IF EXISTS _rtree_check")
        except sqlite3.OperationalError as e:
            raise RuntimeError(
                "SQLite R-Tree extension required but not available. "
                "Rebuild SQLite with --enable-rtree or use a distribution that includes it."
            ) from e

        self.conn.executescript(INDEX_SCHEMA_SQL)
        self.conn.executescript(RTREE_SCHEMA_SQL)

        # Set schema version
        self.conn.execute(
            "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES ('schema_version', ?)",
            (INDEX_SCHEMA_VERSION,),
        )
        self.conn.commit()

    def needs_rebuild(self) -> bool:
        """Check if the schema version matches."""
        try:
            row = self.conn.execute("SELECT value FROM cache_metadata WHERE key = 'schema_version'").fetchone()
            if row is None:
                return True
            return str(row["value"]) != INDEX_SCHEMA_VERSION
        except sqlite3.OperationalError:
            return True

    def clear(self) -> None:
        """Delete all data from all tables."""
        self.conn.execute("DELETE FROM symbol_containments")
        self.conn.execute("DELETE FROM definition_ranges")
        self.conn.execute("DELETE FROM symbols")
        self.conn.execute("DELETE FROM source_files")
        self.conn.execute("DELETE FROM cache_metadata")
        self.conn.commit()

    def get_status(self) -> dict[str, Any]:
        """Return counts and metadata about the index."""
        c = self.conn
        files = c.execute("SELECT COUNT(*) FROM source_files").fetchone()[0]
        total_syms = c.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        defs = c.execute("SELECT COUNT(*) FROM symbols WHERE is_definition = 1").fetchone()[0]
        refs = c.execute("SELECT COUNT(*) FROM symbols WHERE is_definition = 0").fetchone()[0]
        containments = c.execute("SELECT COUNT(*) FROM symbol_containments").fetchone()[0]
        languages = [
            row[0] for row in c.execute("SELECT DISTINCT language FROM source_files ORDER BY language").fetchall()
        ]
        return {
            "files": files,
            "symbols": total_syms,
            "definitions": defs,
            "references": refs,
            "containments": containments,
            "languages": languages,
            "db_path": str(self._db_path),
            "schema_version": INDEX_SCHEMA_VERSION,
        }

    # ------------------------------------------------------------------
    # File discovery
    # ------------------------------------------------------------------

    def discover_files(self, root_path: Path) -> list[dict[str, Any]]:
        """Discover source files using git ls-files, falling back to rglob."""
        try:
            result = subprocess.run(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                cwd=str(root_path),
                capture_output=True,
                text=True,
                check=True,
            )
            raw_paths = result.stdout.strip().splitlines()
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Not a git repo or git not available — use rglob
            raw_paths = []
            for ext in SUPPORTED_EXTENSIONS:
                for p in root_path.rglob(f"*{ext}"):
                    try:
                        raw_paths.append(str(p.relative_to(root_path)))
                    except ValueError:
                        pass

        files: list[dict[str, Any]] = []
        for rel in raw_paths:
            ext = Path(rel).suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            abs_path = (root_path / rel).resolve()
            if not abs_path.is_file():
                continue
            stat = abs_path.stat()
            lang = EXTENSION_TO_LANGUAGE[ext]
            server_cmd = SERVER_COMMANDS[lang][0]
            files.append(
                {
                    "filepath": str(abs_path),
                    "relative_path": rel,
                    "mtime": stat.st_mtime,
                    "size_bytes": stat.st_size,
                    "language": lang,
                    "lsp_server": server_cmd,
                    "file_type": classify_file_type(rel),
                }
            )
        return files

    def get_files_needing_update(self, files: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter to files not yet indexed or with newer mtime."""
        needs_update: list[dict[str, Any]] = []
        for f in files:
            row = self.conn.execute(
                "SELECT mtime FROM source_files WHERE filepath = ?",
                (f["filepath"],),
            ).fetchone()
            if row is None or f["mtime"] > row["mtime"]:
                needs_update.append(f)
        return needs_update

    def get_high_watermark(self) -> float:
        """Return the max mtime from indexed files, or 0.0 if none."""
        row = self.conn.execute("SELECT MAX(mtime) FROM source_files").fetchone()
        return float(row[0]) if row and row[0] is not None else 0.0

    def remove_stale_files(self, current_files: set[str]) -> int:
        """Remove source_files entries not in current_files. Returns count removed."""
        existing = {row[0] for row in self.conn.execute("SELECT filepath FROM source_files").fetchall()}
        stale = existing - current_files
        if stale:
            placeholders = ",".join("?" for _ in stale)
            self.conn.execute(
                f"DELETE FROM source_files WHERE filepath IN ({placeholders})",  # noqa: S608
                list(stale),
            )
            self.conn.commit()
        return len(stale)

    # ------------------------------------------------------------------
    # Indexing pipeline
    # ------------------------------------------------------------------

    def _upsert_source_file(self, file_info: dict[str, Any]) -> int:
        """Insert or update a source file record. Returns the source_file_id."""
        now = datetime.datetime.now(tz=datetime.UTC).isoformat()
        self.conn.execute(
            """\
            INSERT INTO source_files (filepath, relative_path, mtime, size_bytes, indexed_at,
                                      language, lsp_server, file_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(filepath) DO UPDATE SET
                mtime = excluded.mtime,
                size_bytes = excluded.size_bytes,
                indexed_at = excluded.indexed_at
            """,
            (
                file_info["filepath"],
                file_info["relative_path"],
                file_info["mtime"],
                file_info["size_bytes"],
                now,
                file_info["language"],
                file_info["lsp_server"],
                file_info["file_type"],
            ),
        )
        # Get the id
        row = self.conn.execute(
            "SELECT id FROM source_files WHERE filepath = ?",
            (file_info["filepath"],),
        ).fetchone()
        assert row is not None
        return int(row["id"])

    def _clear_file_symbols(self, source_file_id: int) -> None:
        """Remove all symbols and R-Tree entries for a file before re-indexing."""
        # R-Tree entries reference symbol ids, so delete them first
        self.conn.execute(
            """\
            DELETE FROM definition_ranges WHERE id IN (
                SELECT id FROM symbols WHERE source_file_id = ?
            )
            """,
            (source_file_id,),
        )
        self.conn.execute(
            "DELETE FROM symbols WHERE source_file_id = ?",
            (source_file_id,),
        )

    def _index_file_definitions(self, session: LspSession, file_path: Path, source_file_id: int) -> int:
        """Index definitions via documentSymbol. Returns count of definitions inserted."""
        raw_symbols = session.document_symbol(file_path)
        cursor = self.conn.cursor()
        count = self._walk_symbol_tree(cursor, raw_symbols, source_file_id)
        self.conn.commit()
        return count

    def _walk_symbol_tree(self, cursor: sqlite3.Cursor, symbols: list[dict[str, Any]], sf_id: int) -> int:
        """Recursively walk documentSymbol tree and insert definitions."""
        count = 0
        for sym in symbols:
            name = sym.get("name", "")
            kind_num = sym.get("kind", 0)
            kind = _symbol_kind_name(kind_num)

            rng = sym.get("range", {})
            start = rng.get("start", {})
            end = rng.get("end", {})
            line = start.get("line", 0) + 1  # 1-indexed
            col = start.get("character", 0) + 1
            end_line = end.get("line", 0) + 1
            end_col = end.get("character", 0) + 1

            # Selection range for definition location
            sel = sym.get("selectionRange")
            if sel:
                line = sel["start"]["line"] + 1
                col = sel["start"]["character"] + 1

            detail = sym.get("detail")

            # Scope range = full range of the symbol
            scope_start = start.get("line", 0) + 1
            scope_end = end.get("line", 0) + 1

            try:
                cursor.execute(
                    """\
                    INSERT INTO symbols (source_file_id, name, kind, line, col,
                                        end_line, end_col, detail, is_definition,
                                        scope_start_line, scope_end_line)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        sf_id,
                        name,
                        kind,
                        line,
                        col,
                        end_line,
                        end_col,
                        detail,
                        scope_start,
                        scope_end,
                    ),
                )
                sym_id = cursor.lastrowid
                assert sym_id is not None

                # Insert R-Tree entry
                cursor.execute(
                    "INSERT INTO definition_ranges (id, min_line, max_line, min_file_id, max_file_id) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (sym_id, scope_start, scope_end, sf_id, sf_id),
                )
                count += 1
            except sqlite3.IntegrityError:
                log.debug("Duplicate definition skipped: %s at %d:%d", name, line, col)

            # Recurse into children
            children = sym.get("children", [])
            if children:
                count += self._walk_symbol_tree(cursor, children, sf_id)

        return count

    def _index_file_tokens(
        self,
        session: LspSession,
        file_path: Path,
        source_file_id: int,
        legend: dict[str, Any],
    ) -> int:
        """Index references via semanticTokens/full. Returns count of refs inserted.

        RETAINED BUT NOT THE DEFAULT. Open-source pyright does not implement
        semanticTokens, so this returns 0 against a Python workspace and always
        will. `--edges callhierarchy` is the supported path. Kept because
        typescript-language-server does implement it, and because a token index
        answers a different question (every mention) than a call graph does.
        """
        try:
            result = session.semantic_tokens(file_path)
        except (JsonRpcError, TimeoutError) as e:
            log.warning("semanticTokens failed for %s: %s", file_path, e)
            return 0

        data = result.get("data", [])
        if not data:
            # The silent-zero that made the original index look healthy and be
            # empty. Say so, loudly, every time.
            log.warning(
                "semanticTokens returned no data for %s: the server does not implement it. "
                "Use --edges callhierarchy.",
                file_path.name,
            )
            return 0

        source_text = _read_file_text(file_path)
        tokens = decode_semantic_tokens(data, legend, source_text)

        count = 0
        cursor = self.conn.cursor()
        for tok in tokens:
            # Skip tokens that are definitions — already inserted by documentSymbol
            if tok["is_definition"]:
                continue
            try:
                cursor.execute(
                    """\
                    INSERT INTO symbols (source_file_id, name, kind, line, col,
                                        end_line, end_col, is_definition)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        source_file_id,
                        tok["name"],
                        tok["kind"],
                        tok["line"],
                        tok["col"],
                        tok["end_line"],
                        tok["end_col"],
                    ),
                )
                count += 1
            except sqlite3.IntegrityError:
                pass  # Duplicate token position (definition already exists)

        self.conn.commit()
        return count

    def _populate_containments(self) -> int:
        """Build the symbol_containments edge list from R-Tree data.

        For each symbol, find its immediate enclosing definition
        (smallest scope that contains it).
        """
        self.conn.execute("DELETE FROM symbol_containments")

        result = self.conn.execute(
            """\
            INSERT INTO symbol_containments (inner_symbol_id, outer_symbol_id)
            SELECT s.id, (
                SELECT dr.id FROM definition_ranges dr
                WHERE dr.min_line <= s.line AND dr.max_line >= s.line
                  AND dr.min_file_id = s.source_file_id
                  AND dr.max_file_id = s.source_file_id
                  AND dr.id != s.id
                ORDER BY (dr.max_line - dr.min_line) ASC
                LIMIT 1
            )
            FROM symbols s
            WHERE (
                SELECT dr.id FROM definition_ranges dr
                WHERE dr.min_line <= s.line AND dr.max_line >= s.line
                  AND dr.min_file_id = s.source_file_id
                  AND dr.max_file_id = s.source_file_id
                  AND dr.id != s.id
                ORDER BY (dr.max_line - dr.min_line) ASC
                LIMIT 1
            ) IS NOT NULL
            """
        )
        count = result.rowcount
        self.conn.commit()
        return count

    # -- call-hierarchy edges -------------------------------------------------

    def _index_file_calls(
        self,
        session: LspSession,
        file_path: Path,
        source_file_id: int,
    ) -> int:
        """Index real call edges via prepareCallHierarchy + incomingCalls.

        This is the replacement for `_index_file_tokens`. A row is written per
        (caller definition, callee definition) pair with the call-site count, so
        both readings are available downstream: count rows for distinct callers,
        sum `sites` for call sites.

        Requires every file in the workspace to have been opened first. Servers
        default to analysing open files only and answer a position in an
        unopened file with a plausible, wrong, empty result rather than an error.
        """
        cursor = self.conn.cursor()
        defs = cursor.execute(
            """
            SELECT id, name, line, col FROM symbols
            WHERE source_file_id = ? AND is_definition = 1
              AND kind IN ('function', 'method', 'constructor')
            """,
            (source_file_id,),
        ).fetchall()

        count = 0
        for sym_id, name, line, col in defs:
            if ANONYMOUS_SYMBOL.search(name or ""):
                continue
            try:
                items = session.prepare_call_hierarchy(file_path, line, col)
            except (JsonRpcError, TimeoutError) as e:
                log.warning("prepareCallHierarchy failed for %s:%s: %s", file_path.name, line, e)
                continue
            if not items:
                continue
            try:
                callers = session.incoming_calls(items[0])
            except (JsonRpcError, TimeoutError) as e:
                log.warning("incomingCalls failed for %s:%s: %s", file_path.name, line, e)
                continue

            for caller, sites in callers:
                loc = _caller_location(caller)
                if loc is None:
                    continue
                caller_abs, caller_line = loc
                # The kind filter is load-bearing. A parameter is reported as a
                # variable definition on the SAME line as its function, so
                # matching on line alone returns `harness_name` where the caller
                # is `invocation`. That silently halved the edge count.
                row = cursor.execute(
                    """
                    SELECT s.id FROM symbols s
                    JOIN source_files sf ON sf.id = s.source_file_id
                    WHERE sf.filepath = ? AND s.line = ? AND s.is_definition = 1
                      AND s.kind IN ('function', 'method', 'constructor')
                    LIMIT 1
                    """,
                    (caller_abs, caller_line),
                ).fetchone()
                if row is None or row[0] == sym_id:
                    continue
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO call_edges (caller_symbol_id, callee_symbol_id, sites)
                    VALUES (?, ?, ?)
                    """,
                    (row[0], sym_id, sites),
                )
                count += 1
        self.conn.commit()
        return count

    def index_files(
        self,
        root_path: Path,
        files: list[dict[str, Any]],
        timeout: float = DEFAULT_TIMEOUT,
    ) -> dict[str, Any]:
        """Index a batch of files, grouped by language for LSP session reuse."""
        # Group by language
        by_lang: dict[str, list[dict[str, Any]]] = {}
        for f in files:
            lang = f["language"]
            if lang not in by_lang:
                by_lang[lang] = []
            by_lang[lang].append(f)

        stats: dict[str, Any] = {
            "files_indexed": 0,
            "definitions": 0,
            "references": 0,
            "call_edges": 0,
            "errors": [],
        }

        for lang, lang_files in by_lang.items():
            server_binary = SERVER_COMMANDS[lang][0]
            if shutil.which(server_binary) is None:
                # A missing server is a missing hard requirement, not a warning.
                # The original appended this to `errors` and exited 0 with
                # files_indexed = 0, which reads as success and is not.
                raise ServerNotFound(lang, server_binary)

            mgr = LanguageServerManager(lang)
            try:
                session = mgr.start(self.lsp_root or root_path)

                # Pass 1: definitions. Every file is opened and STAYS open.
                #
                # The original closed each file as soon as it was indexed, to
                # save server memory. That is exactly the openFilesOnly trap:
                # by the time file N is queried, files 1..N-1 are closed, so
                # their calls are invisible and the server answers with an
                # empty result rather than an error. Holding every document
                # open is what makes the call graph whole, and it is the single
                # change that took this repository from 0 edges to 380.
                opened: list[Path] = []
                sf_ids: list[tuple[Path, int]] = []
                for file_info in lang_files:
                    fp = Path(file_info["filepath"])
                    sf_id = self._upsert_source_file(file_info)
                    self._clear_file_symbols(sf_id)
                    try:
                        session.did_open(fp)
                        opened.append(fp)
                        stats["definitions"] += self._index_file_definitions(session, fp, sf_id)
                        stats["files_indexed"] += 1
                        sf_ids.append((fp, sf_id))
                    except (TimeoutError, JsonRpcError, OSError) as e:
                        stats["errors"].append(f"{file_info['relative_path']}: {e}")
                        log.warning("Error indexing %s: %s", fp, e)

                log.info("%s: %d definitions across %d open documents",
                         lang, stats["definitions"], len(opened))

                # Pass 2: edges, with the whole workspace still resident.
                if self.edge_source == "callhierarchy":
                    for fp, sf_id in sf_ids:
                        try:
                            stats["call_edges"] += self._index_file_calls(session, fp, sf_id)
                        except (TimeoutError, JsonRpcError, OSError) as e:
                            stats["errors"].append(f"callHierarchy {fp.name}: {e}")
                else:
                    legend = session.semantic_tokens_legend
                    for fp, sf_id in sf_ids:
                        if legend:
                            stats["references"] += self._index_file_tokens(session, fp, sf_id, legend)

                for fp in opened:
                    session.did_close(fp)

            except (ServerNotFound, OSError) as e:
                stats["errors"].append(f"Failed to start {lang} server: {e}")
                raise
            finally:
                mgr.stop()

        if stats["files_indexed"] and not stats["call_edges"] and not stats["references"]:
            # An index with definitions and no edges is the failure this fork
            # exists to stop shipping silently.
            log.error(
                "Indexed %d files and %d definitions but found NO edges. "
                "The call graph is empty and any score computed from it is meaningless.",
                stats["files_indexed"],
                stats["definitions"],
            )

        return stats

    def update(self, root_path: Path, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
        """Full rebuild: discover files, index all, build containments."""
        if self.needs_rebuild():
            self.init_schema()

        files = self.discover_files(root_path)
        current = {f["filepath"] for f in files}
        stale = self.remove_stale_files(current)

        stats = self.index_files(root_path, files, timeout)
        containments = self._populate_containments()

        stats["stale_removed"] = stale
        stats["containments"] = containments
        stats["total_files_discovered"] = len(files)
        return stats

    def update_incremental(self, root_path: Path, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
        """Incremental: only index files with newer mtime."""
        if self.needs_rebuild():
            self.init_schema()

        files = self.discover_files(root_path)
        current = {f["filepath"] for f in files}
        stale = self.remove_stale_files(current)

        needs_update = self.get_files_needing_update(files)
        stats = self.index_files(root_path, needs_update, timeout)
        containments = self._populate_containments()

        stats["stale_removed"] = stale
        stats["containments"] = containments
        stats["total_files_discovered"] = len(files)
        stats["files_skipped"] = len(files) - len(needs_update)
        return stats


# ============================================================================
# Layer 6: CLI Interface
# ============================================================================


def _output_json(data: Any, *, pretty: bool = False) -> None:
    """Output JSON to stdout — compact by default, indented with --pretty."""
    if pretty:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(data, separators=(",", ":"), ensure_ascii=False))


def _error_json(message: str, hint: str | None = None) -> None:
    """Output error as JSON to stderr."""
    err: dict[str, str] = {"error": message}
    if hint:
        err["hint"] = hint
    print(json.dumps(err, separators=(",", ":")), file=sys.stderr)


def cmd_symbols(args: argparse.Namespace) -> int:
    """Handle the 'symbols' command."""
    explorer = CodeExplorer(root_path=args.root, timeout=args.timeout)
    result = explorer.symbols(Path(args.file))
    _output_json(result, pretty=args.pretty)
    return 0


def cmd_definition(args: argparse.Namespace) -> int:
    """Handle the 'definition' command."""
    explorer = CodeExplorer(root_path=args.root, timeout=args.timeout)
    result = explorer.definition(Path(args.file), args.line, args.col)
    _output_json(result, pretty=args.pretty)
    return 0


def cmd_references(args: argparse.Namespace) -> int:
    """Handle the 'references' command."""
    explorer = CodeExplorer(root_path=args.root, timeout=args.timeout)
    result = explorer.references(Path(args.file), args.line, args.col)
    _output_json(result, pretty=args.pretty)
    return 0


def cmd_hover(args: argparse.Namespace) -> int:
    """Handle the 'hover' command."""
    explorer = CodeExplorer(root_path=args.root, timeout=args.timeout)
    result = explorer.hover(Path(args.file), args.line, args.col)
    if result is None:
        _output_json({}, pretty=args.pretty)
    else:
        _output_json(result, pretty=args.pretty)
    return 0


def cmd_diagnostics(args: argparse.Namespace) -> int:
    """Handle the 'diagnostics' command."""
    explorer = CodeExplorer(root_path=args.root, timeout=args.timeout)
    result = explorer.diagnostics(Path(args.file))
    _output_json(result, pretty=args.pretty)
    return 0


def cmd_explore(args: argparse.Namespace) -> int:
    """Handle the 'explore' command."""
    explorer = CodeExplorer(root_path=args.root, timeout=args.timeout)
    result = explorer.explore(Path(args.file))
    _output_json(result, pretty=args.pretty)
    return 0


def cmd_impact(args: argparse.Namespace) -> int:
    """Handle the 'impact' command."""
    explorer = CodeExplorer(root_path=args.root, timeout=args.timeout)
    result = explorer.impact(Path(args.file), args.line, args.col, depth=args.depth)
    _output_json(result, pretty=args.pretty)
    return 0


# --- Index / cache commands (no live LSP needed for queries) ---


def _get_cache_manager(args: argparse.Namespace) -> IndexCacheManager:
    """Create an IndexCacheManager, optionally with a custom db path."""
    db_path = getattr(args, "db_path", None)
    edges = getattr(args, "edges", "callhierarchy")
    lsp_root = getattr(args, "lsp_root", None)
    if db_path:
        mgr = IndexCacheManager(db_path=Path(db_path), edge_source=edges)
        mgr.lsp_root = Path(lsp_root).resolve() if lsp_root else None
        return mgr
    mgr = IndexCacheManager(edge_source=edges)
    mgr.lsp_root = Path(lsp_root).resolve() if lsp_root else None
    return mgr


def cmd_index(args: argparse.Namespace) -> int:
    """Build the symbol index."""
    root = args.root or Path.cwd()
    cache = _get_cache_manager(args)
    try:
        cache_mode = getattr(args, "cache_mode", "rebuild")
        if cache_mode == "frozen":
            _output_json({"status": "frozen", "message": "Using existing cache as-is"}, pretty=args.pretty)
            return 0

        if cache_mode == "rebuild":
            if not cache.needs_rebuild():
                cache.clear()
            cache.init_schema()
            stats = cache.update(root, timeout=args.timeout)
        else:  # incremental
            cache.init_schema()
            stats = cache.update_incremental(root, timeout=args.timeout)

        _output_json(stats, pretty=args.pretty)
        return 0
    finally:
        cache.close()


def cmd_index_status(args: argparse.Namespace) -> int:
    """Show index statistics."""
    cache = _get_cache_manager(args)
    try:
        if cache.needs_rebuild():
            _output_json(
                {"status": "no_index", "message": "No index found. Run 'index' first."},
                pretty=args.pretty,
            )
            return 0
        status = cache.get_status()
        _output_json(status, pretty=args.pretty)
        return 0
    finally:
        cache.close()


def cmd_index_clear(args: argparse.Namespace) -> int:
    """Clear all index data."""
    cache = _get_cache_manager(args)
    try:
        cache.init_schema()
        cache.clear()
        _output_json({"status": "cleared"}, pretty=args.pretty)
        return 0
    finally:
        cache.close()


def cmd_lookup(args: argparse.Namespace) -> int:
    """Find definitions by name."""
    cache = _get_cache_manager(args)
    try:
        if cache.needs_rebuild():
            _error_json("No index found. Run 'index' first.")
            return 1

        query = "SELECT s.name, s.kind, sf.relative_path, s.line, s.col, sf.file_type"
        query += " FROM symbols s JOIN source_files sf ON sf.id = s.source_file_id"
        query += " WHERE s.is_definition = 1 AND s.name LIKE ?"
        params: list[Any] = [f"%{args.name}%"]

        if getattr(args, "kind", None):
            query += " AND s.kind = ?"
            params.append(args.kind)
        if getattr(args, "file_type", None):
            query += " AND sf.file_type = ?"
            params.append(args.file_type)

        query += " ORDER BY sf.relative_path, s.line"

        rows = cache.conn.execute(query, params).fetchall()
        results = [
            {
                "name": r["name"],
                "kind": r["kind"],
                "file": r["relative_path"],
                "line": r["line"],
                "col": r["col"],
                "file_type": r["file_type"],
            }
            for r in rows
        ]
        _output_json(results, pretty=args.pretty)
        return 0
    finally:
        cache.close()


def cmd_dead(args: argparse.Namespace) -> int:
    """Find unreferenced definitions (dead code candidates)."""
    cache = _get_cache_manager(args)
    try:
        if cache.needs_rebuild():
            _error_json("No index found. Run 'index' first.")
            return 1

        query = """\
            SELECT s.name, s.kind, sf.relative_path, s.line, sf.file_type
            FROM symbols s
            JOIN source_files sf ON sf.id = s.source_file_id
            WHERE s.is_definition = 1
              AND s.kind NOT IN ('module', 'package', 'namespace')
              AND NOT EXISTS (
                  SELECT 1 FROM symbols ref
                  WHERE ref.name = s.name
                    AND ref.id != s.id
                    AND ref.is_definition = 0
              )
        """
        params: list[Any] = []

        if getattr(args, "kind", None):
            query += " AND s.kind = ?"
            params.append(args.kind)
        if getattr(args, "file_type", None):
            query += " AND sf.file_type = ?"
            params.append(args.file_type)
        if getattr(args, "exclude_private", False):
            query += " AND s.name NOT LIKE '\\_%' ESCAPE '\\'"

        query += " ORDER BY sf.relative_path, s.line"

        rows = cache.conn.execute(query, params).fetchall()
        results = [
            {
                "name": r["name"],
                "kind": r["kind"],
                "file": r["relative_path"],
                "line": r["line"],
                "file_type": r["file_type"],
            }
            for r in rows
        ]
        _output_json({"dead": results, "count": len(results)}, pretty=args.pretty)
        return 0
    finally:
        cache.close()


def cmd_trace(args: argparse.Namespace) -> int:
    """Impact analysis from cached index using recursive CTEs."""
    cache = _get_cache_manager(args)
    try:
        if cache.needs_rebuild():
            _error_json("No index found. Run 'index' first.")
            return 1

        # Find the definition at the given position (match on relative_path)
        file_path = args.file
        row = cache.conn.execute(
            """\
            SELECT s.id, s.name FROM symbols s
            JOIN source_files sf ON sf.id = s.source_file_id
            WHERE sf.relative_path = ? AND s.line = ? AND s.col = ? AND s.is_definition = 1
            LIMIT 1
            """,
            (file_path, args.line, args.col),
        ).fetchone()

        if row is None:
            # Try fuzzy match on line only
            row = cache.conn.execute(
                """\
                SELECT s.id, s.name FROM symbols s
                JOIN source_files sf ON sf.id = s.source_file_id
                WHERE sf.relative_path = ? AND s.line = ? AND s.is_definition = 1
                LIMIT 1
                """,
                (file_path, args.line),
            ).fetchone()

        if row is None:
            _error_json("No definition found at the specified position")
            return 1

        start_id = row["id"]
        max_depth = getattr(args, "depth", 3)

        rows = cache.conn.execute(
            """\
            WITH RECURSIVE impact_chain(sym_id, name, source_file_id, depth) AS (
                SELECT s.id, s.name, s.source_file_id, 0
                FROM symbols s
                WHERE s.id = ? AND s.is_definition = 1

                UNION ALL

                SELECT enclosing.id, enclosing.name, enclosing.source_file_id, ic.depth + 1
                FROM impact_chain ic
                JOIN symbols ref ON ref.name = ic.name AND ref.is_definition = 0
                JOIN symbol_containments sc ON sc.inner_symbol_id = ref.id
                JOIN symbols enclosing ON enclosing.id = sc.outer_symbol_id
                WHERE ic.depth < ?
            )
            SELECT DISTINCT ic.depth, ic.name, s.kind, sf.relative_path, s.line,
                   s.scope_start_line, s.scope_end_line
            FROM impact_chain ic
            JOIN symbols s ON s.id = ic.sym_id
            JOIN source_files sf ON sf.id = ic.source_file_id
            ORDER BY ic.depth, sf.relative_path, s.line
            """,
            (start_id, max_depth),
        ).fetchall()

        results = [
            {
                "depth": r["depth"],
                "name": r["name"],
                "kind": r["kind"],
                "file": r["relative_path"],
                "line": r["line"],
                "scope": [r["scope_start_line"], r["scope_end_line"]],
            }
            for r in rows
        ]
        _output_json({"trace": results, "count": len(results)}, pretty=args.pretty)
        return 0
    finally:
        cache.close()


def cmd_files(args: argparse.Namespace) -> int:
    """List indexed files."""
    cache = _get_cache_manager(args)
    try:
        if cache.needs_rebuild():
            _error_json("No index found. Run 'index' first.")
            return 1

        query = "SELECT relative_path, language, file_type, mtime FROM source_files WHERE 1=1"
        params: list[Any] = []

        if getattr(args, "language", None):
            query += " AND language = ?"
            params.append(args.language)
        if getattr(args, "file_type", None):
            query += " AND file_type = ?"
            params.append(args.file_type)

        query += " ORDER BY relative_path"

        rows = cache.conn.execute(query, params).fetchall()
        results = [
            {
                "file": r["relative_path"],
                "language": r["language"],
                "file_type": r["file_type"],
            }
            for r in rows
        ]
        _output_json({"files": results, "count": len(results)}, pretty=args.pretty)
        return 0
    finally:
        cache.close()


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Uses a shared parent parser so flags like --root, --pretty, --timeout
    work both before AND after the subcommand name.
    """
    # Shared flags inherited by every subcommand via parents=[]
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    common.add_argument("--pretty", action="store_true", help="Pretty-print JSON output (indent=2)")
    common.add_argument("--root", type=Path, default=None, help="Override project root directory")
    common.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )

    # Cache control flags — shared parent for index-related commands
    cache_parent = argparse.ArgumentParser(add_help=False)
    # _get_cache_manager has always read args.db_path, but no flag ever set it,
    # so every invocation wrote to the one default cache. This fork needs its
    # own database anyway, so that the skill's index is not clobbered.
    cache_parent.add_argument(
        "--db-path",
        default=None,
        help="SQLite index location (default: .claude/cache/lsp_index.db)",
    )
    cache_parent.add_argument(
        "--lsp-root",
        default=None,
        help=(
            "workspace root for the language server, when it differs from --root. "
            "A TypeScript app in a subdirectory needs its own package root, and "
            "pointing pyright below the project root costs you edges."
        ),
    )
    cache_group = cache_parent.add_mutually_exclusive_group()
    cache_group.add_argument(
        "--cache-frozen",
        action="store_const",
        const="frozen",
        dest="cache_mode",
        help="Skip indexing, use existing cache as-is",
    )
    cache_group.add_argument(
        "--cache-incremental",
        action="store_const",
        const="incremental",
        dest="cache_mode",
        help="Only index files with newer mtime",
    )
    cache_group.add_argument(
        "--cache-rebuild",
        action="store_const",
        const="rebuild",
        dest="cache_mode",
        help="Wipe and rebuild entire index (default)",
    )
    cache_parent.set_defaults(cache_mode="rebuild")

    parser = argparse.ArgumentParser(
        prog="lsp_explorer",
        description=(
            "Query language servers for code intelligence — symbols, definitions,"
            " references, hover, diagnostics, and impact analysis."
        ),
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- Live LSP commands ---

    # symbols
    p_sym = subparsers.add_parser("symbols", parents=[common], help="List symbols in a file")
    p_sym.add_argument("file", help="File to analyze")
    p_sym.set_defaults(func=cmd_symbols)

    # definition
    p_def = subparsers.add_parser("definition", parents=[common], help="Go to definition of symbol at position")
    p_def.add_argument("file", help="File containing the symbol")
    p_def.add_argument("line", type=int, help="Line number (1-indexed)")
    p_def.add_argument("col", type=int, help="Column number (1-indexed)")
    p_def.set_defaults(func=cmd_definition)

    # references
    p_ref = subparsers.add_parser("references", parents=[common], help="Find all references to symbol at position")
    p_ref.add_argument("file", help="File containing the symbol")
    p_ref.add_argument("line", type=int, help="Line number (1-indexed)")
    p_ref.add_argument("col", type=int, help="Column number (1-indexed)")
    p_ref.set_defaults(func=cmd_references)

    # hover
    p_hov = subparsers.add_parser("hover", parents=[common], help="Get hover info (type signature, docs) at position")
    p_hov.add_argument("file", help="File containing the symbol")
    p_hov.add_argument("line", type=int, help="Line number (1-indexed)")
    p_hov.add_argument("col", type=int, help="Column number (1-indexed)")
    p_hov.set_defaults(func=cmd_hover)

    # diagnostics
    p_diag = subparsers.add_parser(
        "diagnostics", parents=[common], help="Get diagnostics (errors, warnings) for a file"
    )
    p_diag.add_argument("file", help="File to check")
    p_diag.set_defaults(func=cmd_diagnostics)

    # explore
    p_exp = subparsers.add_parser("explore", parents=[common], help="Combined symbols + diagnostics overview")
    p_exp.add_argument("file", help="File to explore")
    p_exp.set_defaults(func=cmd_explore)

    # impact (live LSP)
    p_imp = subparsers.add_parser("impact", parents=[common], help="Analyze change impact (multi-hop references)")
    p_imp.add_argument("file", help="File containing the symbol")
    p_imp.add_argument("line", type=int, help="Line number (1-indexed)")
    p_imp.add_argument("col", type=int, help="Column number (1-indexed)")
    p_imp.add_argument("--depth", type=int, default=1, help="Reference trace depth (default: 1)")
    p_imp.set_defaults(func=cmd_impact)

    # --- Index / cache commands ---

    # index
    p_idx = subparsers.add_parser("index", parents=[common, cache_parent], help="Build symbol index for a project")
    p_idx.add_argument(
        "--edges",
        choices=["callhierarchy", "tokens"],
        default="callhierarchy",
        help=(
            "how to derive edges. 'callhierarchy' (default) writes real call edges and "
            "works with pyright. 'tokens' is the original semanticTokens path, which "
            "pyright does not implement and which yields nothing on Python."
        ),
    )
    p_idx.set_defaults(func=cmd_index)

    # index-status
    p_idx_st = subparsers.add_parser("index-status", parents=[common], help="Show index statistics")
    p_idx_st.set_defaults(func=cmd_index_status)

    # index-clear
    p_idx_cl = subparsers.add_parser("index-clear", parents=[common], help="Wipe all index data")
    p_idx_cl.set_defaults(func=cmd_index_clear)

    # lookup
    p_look = subparsers.add_parser("lookup", parents=[common], help="Find definitions by name (cached)")
    p_look.add_argument("name", help="Symbol name (substring match)")
    p_look.add_argument("--kind", help="Filter by kind (class, function, etc.)")
    p_look.add_argument("--file-type", choices=["source", "test"], help="Filter by file type")
    p_look.set_defaults(func=cmd_lookup)

    # dead
    p_dead = subparsers.add_parser("dead", parents=[common], help="Find unreferenced definitions (cached)")
    p_dead.add_argument("--kind", help="Filter by kind (class, function, etc.)")
    p_dead.add_argument("--file-type", choices=["source", "test"], help="Filter by file type")
    p_dead.add_argument("--exclude-private", action="store_true", help="Exclude _private names")
    p_dead.set_defaults(func=cmd_dead)

    # trace
    p_trace = subparsers.add_parser("trace", parents=[common], help="Impact analysis from cached index")
    p_trace.add_argument("file", help="File containing the definition")
    p_trace.add_argument("line", type=int, help="Line number (1-indexed)")
    p_trace.add_argument("col", type=int, help="Column number (1-indexed)")
    p_trace.add_argument("--depth", type=int, default=3, help="Max trace depth (default: 3)")
    p_trace.set_defaults(func=cmd_trace)

    # files
    p_files = subparsers.add_parser("files", parents=[common], help="List indexed files (cached)")
    p_files.add_argument("--language", help="Filter by language (python, typescript, javascript)")
    p_files.add_argument("--file-type", choices=["source", "test"], help="Filter by file type")
    p_files.set_defaults(func=cmd_files)

    return parser


def main(args: argparse.Namespace) -> int:
    """Main entry point."""
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)

    try:
        ret: int = args.func(args)
        return ret
    except ServerNotFound as e:
        _error_json(str(e), hint=f"Install the {e.language} language server")
        return 1
    except UnsupportedLanguage as e:
        _error_json(str(e))
        return 1
    except FileNotFoundError as e:
        _error_json(f"File not found: {e}")
        return 1
    except TimeoutError as e:
        _error_json(str(e), hint="Try increasing --timeout")
        return 1
    except JsonRpcError as e:
        _error_json(f"LSP error: {e.error_message} (code {e.code})")
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(build_parser().parse_args()))
