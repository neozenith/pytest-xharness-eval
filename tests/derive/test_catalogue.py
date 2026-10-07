"""``derive.catalogue``: the bundled ``models.toml``, one file for every supported model (ADR 0059)."""

# Standard Library
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.derive import catalogue
from pytest_xharness_eval.model.catalogue import CatalogueError


def test_the_bundled_file_loads_and_names_each_harness_feed_provider() -> None:
    loaded = catalogue.load_catalogue()
    assert loaded.require("codex", "gpt-6-sol").family_tier == 3
    assert {f.harness: f.provider for f in catalogue.feeds()} == {"claude": "anthropic", "codex": "openai"}


@pytest.mark.parametrize(
    ("body", "match"),
    [
        ('[gemini]\nfeed_provider = "google"\n', "unknown harness 'gemini'"),
        ('[codex]\nfeed_provider = "openai"\nprice = 1\n', "expected only"),
        ('[codex]\nfeed_provider = "openai"\n[codex.models."m"]\nline = "x"\ntier = 1\n', "and optionally effort"),
        (
            '[codex]\nfeed_provider = "openai"\n[codex.models."m"]\n'
            'line = "x"\ntier = 1\nreleased = 2026-01-01\neffort = "no"\n',
            "effort must be true or false",
        ),
        (
            '[codex]\nfeed_provider = "openai"\n[codex.models."m"]\nline = "x"\ntier = "1"\nreleased = 2026-01-01\n',
            "tier must be an integer",
        ),
    ],
)
def test_a_malformed_catalogue_file_is_refused(tmp_path: Path, body: str, match: str) -> None:
    path = tmp_path / "models.toml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(CatalogueError, match=match):
        catalogue.load_catalogue(path=path)
