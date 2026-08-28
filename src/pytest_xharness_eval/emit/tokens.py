"""``report/report.tokens.json``: the design tokens the page is themed with (ADR 0024).

Colours, series palettes, category pills and fonts, as one JSON document. The bundled file
ships beside the page; a project points ``xharness_report_design_tokens`` at its own and
the page is rebranded without touching the SPA. The one rule this module exists to hold:
a tokens file the user named must be there and must be a themes document -- a missing or
malformed one is an error, never a silent fallback to the default look.
"""

from __future__ import annotations

# Standard Library
import json
from importlib import resources
from typing import TYPE_CHECKING, Any

# Our Libraries
from pytest_xharness_eval.model.layout import TOKENS_NAME

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path


def load_tokens(path: Path | None = None) -> dict[str, Any]:
    """The design tokens to theme the page with: the user's file when given, else the bundled default.

    A user file must be a JSON object; a missing file is an error, never a silent
    fallback to the default look.
    """
    if path is None:
        raw = resources.files("pytest_xharness_eval").joinpath("assets", TOKENS_NAME).read_text(encoding="utf-8")
    else:
        if not path.is_file():
            raise FileNotFoundError(f"design tokens file not found: {path}")
        raw = path.read_text(encoding="utf-8")
    tokens = json.loads(raw)
    if not isinstance(tokens, dict) or "themes" not in tokens:
        raise ValueError(f"design tokens must be a JSON object with a 'themes' key: {path or TOKENS_NAME}")
    return tokens
