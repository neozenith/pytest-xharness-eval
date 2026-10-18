"""``model.scenario``: a generated fixture's identity, its bytes on disk, and its seeded draws (ADR 0074)."""

# Standard Library
import json
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.model.scenario import (
    PROVENANCE_SUFFIX,
    Draw,
    Scenario,
    fingerprint,
    read_tree,
    slug,
    stored_scenarios,
    write_scenario,
    write_tree,
)


def _scenario(**overrides: object) -> Scenario:
    fields: dict[str, object] = {
        "generator": "gen",
        "params": {"a": 1, "b": "two"},
        "files": {"doc.md": "# Title\n", "sub/data.bin": b"\x00\x01"},
    }
    return Scenario(**(fields | overrides))  # type: ignore[arg-type]


# -- identity --------------------------------------------------------------------


def test_the_same_parameters_name_the_same_scenario_in_any_key_order() -> None:
    """The id is pinned to generator, version and canonical params, never to a position or a counter."""
    first = _scenario()
    again = _scenario(params={"b": "two", "a": 1}, files={"other.md": "different bytes"})
    assert first.id == again.id and first.key == again.key
    assert first.id == "a-1-b-two--" + first.key[:8]


@pytest.mark.parametrize(
    "change",
    [{"version": 2}, {"params": {"a": 2, "b": "two"}}, {"generator": "other"}],
    ids=["version", "params", "generator"],
)
def test_changing_version_params_or_generator_changes_the_id(change: dict[str, object]) -> None:
    assert _scenario(**change).id != _scenario().id


def test_a_label_names_the_id_as_a_slug_and_does_not_move_its_digest() -> None:
    labelled = _scenario(label="Hello, World! / Ünïcode")
    assert labelled.id == f"hello-world-n-code--{_scenario().key[:8]}"
    assert slug("x" * 60) == "x" * 40
    assert slug("!!!") == "scenario"  # nothing readable left still names something


def test_the_fingerprint_is_the_bytes_and_ignores_the_parameters() -> None:
    s = _scenario()
    assert s.fingerprint == fingerprint({"sub/data.bin": b"\x00\x01", "doc.md": b"# Title\n"})
    assert _scenario(params={"z": 9}).fingerprint == s.fingerprint
    assert _scenario(files={"doc.md": "# Title!\n"}).fingerprint != s.fingerprint
    # Path is part of the digest: the same bytes under another name are another input.
    assert fingerprint({"a.md": "x"}) != fingerprint({"b.md": "x"})


def test_a_scenario_with_no_files_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="has no files"):
        _scenario(files={})


@pytest.mark.parametrize("params", [{"x": object()}, {"x": {1, 2}}, {"x": Path("p")}], ids=["object", "set", "path"])
def test_non_json_params_are_refused_at_construction(params: dict[str, object]) -> None:
    """Params are digested, written beside the evidence and read back: a non-JSON one would not round-trip."""
    with pytest.raises(TypeError, match="JSON"):
        _scenario(params=params)


# -- Draw ------------------------------------------------------------------------


def test_a_draw_is_reproducible_from_its_seed_and_differs_for_another() -> None:
    a, b, c = Draw("g", 1, 0), Draw("g", 1, 0), Draw("g", 1, 1)
    first = [a.random() for _ in range(5)]
    assert first == [b.random() for _ in range(5)]
    assert first != [c.random() for _ in range(5)]
    # Pinned: the seed is a sha256 digest and the draws go through random() alone, so this
    # value is the same on every machine, process and supported Python (never hash()).
    assert Draw("pinned").integer(0, 1_000_000) == 171_712


def test_integer_stays_inside_its_closed_range_and_reaches_both_ends() -> None:
    draw = Draw("range")
    seen = {draw.integer(3, 6) for _ in range(400)}
    assert seen == {3, 4, 5, 6}
    assert draw.integer(7, 7) == 7


def test_choice_chance_shuffle_and_sample() -> None:
    draw = Draw("ops")
    assert draw.choice(["only"]) == "only"
    with pytest.raises(ValueError, match="no options"):
        draw.choice([])
    assert not any(draw.chance(0.0) for _ in range(50))
    assert all(draw.chance(1.0) for _ in range(50))
    items = list(range(20))
    shuffled = draw.shuffled(items)
    assert sorted(shuffled) == items and shuffled != items and items == list(range(20))
    picked = draw.sample(items, 5)
    assert len(picked) == len(set(picked)) == 5 and set(picked) <= set(items)


# -- the tree on disk --------------------------------------------------------------


def test_write_tree_empties_its_destination_so_no_stale_file_survives(tmp_path: Path) -> None:
    dest = tmp_path / "s"
    write_tree({"a.md": "a", "deep/nested/b.md": "b"}, dest)
    write_tree({"c.md": b"c"}, dest)
    assert sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*")) == ["c.md"]


@pytest.mark.parametrize("rel", ["../escape.md", "sub/../../escape.md"])
def test_write_tree_refuses_a_path_that_escapes_the_fixture(tmp_path: Path, rel: str) -> None:
    with pytest.raises(ValueError, match="escapes its fixture"):
        write_tree({rel: "x"}, tmp_path / "s")
    assert not (tmp_path / "escape.md").exists()


def test_read_tree_skips_caches_and_vendored_trees_and_needs_a_directory(tmp_path: Path) -> None:
    root = tmp_path / "r"
    write_tree(
        {"a.md": "a", "sub/b.md": "b", "__pycache__/x.pyc": "c", "node_modules/m/i.js": "v", ".git/HEAD": "h"},
        root,
    )
    assert read_tree(root) == {"a.md": b"a", "sub/b.md": b"b"}
    with pytest.raises(FileNotFoundError, match="not a directory"):
        read_tree(tmp_path / "missing")


def test_a_written_scenario_keeps_its_provenance_beside_the_tree_not_inside(tmp_path: Path) -> None:
    """Inside, it would be copied into every workspace and tell the agent how its input was made."""
    s = _scenario(label="lbl", task="Fix doc.md")
    tree = write_scenario(s, tmp_path / "store")
    assert tree == tmp_path / "store" / s.id
    assert sorted(p.name for p in tree.iterdir()) == ["doc.md", "sub"]
    meta = json.loads((tmp_path / "store" / f"{s.id}{PROVENANCE_SUFFIX}").read_text(encoding="utf-8"))
    assert meta == s.provenance()
    assert (meta["generator"], meta["id"], meta["task"], meta["fingerprint"]) == (
        "gen",
        s.id,
        "Fix doc.md",
        s.fingerprint,
    )


def test_rewriting_an_unchanged_scenario_leaves_the_stored_copy_alone(tmp_path: Path) -> None:
    """Every xdist worker collects and writes the same scenario: the second write must be a no-op."""
    s = _scenario()
    tree = write_scenario(s, tmp_path / "store")
    before = {p: (p.stat().st_ino, p.stat().st_mtime_ns) for p in (tree, tree / "doc.md")}
    assert write_scenario(s, tmp_path / "store") == tree
    assert {p: (p.stat().st_ino, p.stat().st_mtime_ns) for p in before} == before


def test_the_same_id_with_new_bytes_replaces_the_stored_copy_and_leaves_no_staging(tmp_path: Path) -> None:
    """A seed file the generator reads was edited: same params, same id, a new fingerprint."""
    store = tmp_path / "store"
    old = _scenario(files={"doc.md": "old\n", "gone.md": "x"})
    write_scenario(old, store)
    new = _scenario(files={"doc.md": "new\n"})
    tree = write_scenario(new, store)
    assert new.id == old.id and sorted(p.name for p in tree.iterdir()) == ["doc.md"]
    assert (tree / "doc.md").read_text(encoding="utf-8") == "new\n"
    assert json.loads((store / f"{new.id}{PROVENANCE_SUFFIX}").read_text(encoding="utf-8"))["fingerprint"] == (
        new.fingerprint
    )
    assert sorted(p.name for p in store.iterdir()) == [new.id, f"{new.id}{PROVENANCE_SUFFIX}"]  # nothing hidden left


def test_stored_scenarios_are_the_trees_with_provenance_beside_them(tmp_path: Path) -> None:
    store = tmp_path / "store"
    assert stored_scenarios(store) == {}
    kept = write_scenario(_scenario(), store)
    (store / "bare-dir").mkdir()  # no provenance: not a stored scenario
    (store / f"orphan{PROVENANCE_SUFFIX}").write_text("{}", encoding="utf-8")  # no tree beside it
    assert stored_scenarios(store) == {kept.name: kept}


def test_a_stored_scenario_reads_back_as_the_same_scenario(tmp_path: Path) -> None:
    s = _scenario(label="lbl", task="Fix it", version=3)
    back = Scenario.promoted(write_scenario(s, tmp_path / "store"))
    assert (back.id, back.fingerprint, back.version, back.label, back.task) == (s.id, s.fingerprint, 3, "lbl", "Fix it")
    assert dict(back.params) == dict(s.params)
    assert back.files == {"doc.md": b"# Title\n", "sub/data.bin": b"\x00\x01"}


def test_a_stored_scenario_whose_bytes_were_edited_is_refused(tmp_path: Path) -> None:
    """A promoted fixture is a frozen reproduction: an edited one would measure a different input under the same id."""
    tree = write_scenario(_scenario(), tmp_path / "store")
    (tree / "doc.md").write_text("# Edited by hand\n", encoding="utf-8")
    with pytest.raises(ValueError, match="re-promote"):
        Scenario.promoted(tree)


def test_a_tree_left_without_provenance_is_a_crashed_write_and_is_replaced(tmp_path: Path) -> None:
    """Provenance is renamed into place last, so a bare tree was never complete, whatever it holds."""
    store = tmp_path / "store"
    s = _scenario()
    write_tree({"doc.md": "half-written", "junk.md": "x"}, store / s.id)
    tree = write_scenario(s, store)
    assert read_tree(tree) == {"doc.md": b"# Title\n", "sub/data.bin": b"\x00\x01"}
    assert sorted(p.name for p in store.iterdir()) == [s.id, f"{s.id}{PROVENANCE_SUFFIX}"]
    assert stored_scenarios(store) == {s.id: tree}


# -- expectations: grader knobs beside the params ------------------------------------


def test_expectations_reach_the_grader_merged_but_never_move_the_id() -> None:
    """Tuning a tolerance keeps a scenario's history in one piece."""
    plain, strict = _scenario(), _scenario(expect={"recall": 0.9})
    assert strict.id == plain.id and strict.key == plain.key
    assert strict.merged == {"a": 1, "b": "two", "recall": 0.9}
    assert plain.merged == {"a": 1, "b": "two"} and dict(plain.expect) == {}
    assert strict.provenance()["expect"] == {"recall": 0.9}


def test_a_key_that_is_both_a_param_and_an_expectation_is_refused() -> None:
    with pytest.raises(ValueError, match=r"\['a'\] is both a param and an expectation"):
        _scenario(expect={"a": 2})


def test_non_json_expectations_are_refused_like_params() -> None:
    with pytest.raises(TypeError, match="JSON"):
        _scenario(expect={"x": {1}})


def test_a_stored_scenario_reads_back_with_its_expectations(tmp_path: Path) -> None:
    s = _scenario(expect={"recall": 0.9})
    back = Scenario.promoted(write_scenario(s, tmp_path / "store"))
    assert dict(back.expect) == {"recall": 0.9} and back.merged == s.merged


def test_a_provenance_written_before_expectations_existed_reads_back_with_none(tmp_path: Path) -> None:
    tree = write_scenario(_scenario(), tmp_path / "store")
    meta = tree.with_name(tree.name + PROVENANCE_SUFFIX)
    old = json.loads(meta.read_text(encoding="utf-8"))
    del old["expect"]
    meta.write_text(json.dumps(old), encoding="utf-8")
    assert dict(Scenario.promoted(tree).expect) == {}
