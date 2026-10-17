"""``harness.threads``: every spawned thread pairs with its spawn record, or the fold stops (ADR 0072)."""

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import Call
from pytest_xharness_eval.harness.threads import PRIMARY, Spawn, SubagentMismatch, Thread, link, span, turn_of_line


def _spawn(key: str, thread: str = PRIMARY, turn: int = 1, *, required: bool = True) -> Spawn:
    return Spawn(thread=thread, turn=turn, id=f"rec-{key}", key=key, required=required)


def _thread(thread_id: str, parent: str = PRIMARY, *keys: str) -> Thread:
    return Thread(id=thread_id, parent=parent, keys=frozenset(keys or {thread_id}))


def test_a_tree_of_threads_is_placed_by_depth_and_credited_to_its_root_turn() -> None:
    links = link(
        [_spawn("a", turn=2), _spawn("b", "a", turn=1), _spawn("c", "b", turn=3)],
        [_thread("c", "b"), _thread("a"), _thread("b", "a")],
    )
    assert {t: (lk.depth, lk.parent_turn, lk.spawn.id) for t, lk in links.items()} == {
        "a": (1, 2, "rec-a"),
        "b": (2, 2, "rec-b"),
        "c": (3, 2, "rec-c"),
    }


def test_a_thread_may_answer_to_any_one_of_its_keys() -> None:
    links = link([_spawn("/root/a")], [_thread("a", PRIMARY, "a", "/root/a")])
    assert links["a"].spawn.key == "/root/a"


@pytest.mark.parametrize(
    ("spawns", "threads", "error"),
    [
        ([_spawn("a"), _spawn("a")], [_thread("a")], "two spawn records name the same thread"),
        ([_spawn("a")], [_thread("a"), _thread("a")], "two subagent transcripts carry the same thread id"),
        ([_spawn("a")], [_thread("x", PRIMARY, "a"), _thread("y", PRIMARY, "a")], "claim one spawn record"),
        ([_spawn("a"), _spawn("/p")], [_thread("a", PRIMARY, "a", "/p")], "named by 2 spawn records"),
        ([], [_thread("a")], "named by 0 spawn records"),
        ([_spawn("a")], [], "no captured subagent transcript: rec-a"),
        ([_spawn("a", "b"), _spawn("b", "a")], [_thread("a", "b"), _thread("b", "a")], "cycle"),
    ],
)
def test_anything_but_an_exact_pairing_stops_the_fold(spawns: list[Spawn], threads: list[Thread], error: str) -> None:
    with pytest.raises(SubagentMismatch, match=error):
        link(spawns, threads)


def test_a_failed_spawn_owes_no_transcript_but_links_one_that_names_it() -> None:
    assert link([_spawn("a", required=False)], []) == {}
    assert link([_spawn("a", required=False)], [_thread("a")])["a"].depth == 1


def test_a_spawn_record_is_credited_to_the_turn_that_holds_its_line() -> None:
    calls = [Call(n=1, at="", records=[1, 2]), Call(n=2, at="", records=[3, 4])]
    assert turn_of_line(calls, 4, "log") == 2
    with pytest.raises(SubagentMismatch, match="line 9 of log belongs to no turn"):
        turn_of_line(calls, 9, "log")


def test_a_span_is_the_earliest_and_latest_timestamp_whatever_order_the_log_wrote_them() -> None:
    early, mid, late = "2026-10-15T11:52:45.805Z", "2026-10-15T11:52:47.325Z", "2026-10-15T11:52:48.469Z"
    records = [(1, {}), (2, {"timestamp": early}), (3, {"timestamp": late}), (4, {"timestamp": mid}), (5, {})]
    assert span(records, "x") == (early, late)


@pytest.mark.parametrize(
    ("records", "error"),
    [
        ([(1, {"type": "user"})], "records no timestamp"),
        ([(1, {"timestamp": "soon"})], "unreadable timestamp 'soon'"),
        ([(1, {"timestamp": "2026-10-15T11:52:45Z"}), (2, {"timestamp": "2026-10-15T11:52:46"})], "mixes zoned"),
    ],
)
def test_a_span_that_cannot_be_read_stops_the_fold(records: list[tuple[int, dict[str, object]]], error: str) -> None:
    with pytest.raises(SubagentMismatch, match=error):
        span(records, "x")
