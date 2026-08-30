import { cleanup, fireEvent, screen } from "@testing-library/react";
import { renderT as render } from "./render";
import { cell, sweep } from "./cells";
import { OverviewFilters } from "@/components/OverviewFilters";
import type { Cell } from "@/lib/types";

const at = (search: string) => history.replaceState(null, "", search ? `/${search}` : "/");
const mount = (cells: Cell[]) => render(<OverviewFilters cells={cells} />);
const chips = (facet: string) => [...document.querySelectorAll<HTMLButtonElement>(`button.filter-chip[data-facet='${facet}']`)];

afterEach(() => at(""));

test("one chip per distinct value per facet, sorted, each showing its cross-filtered count", () => {
  at("?harness=claude");
  mount(sweep());
  expect(chips("harness").map((c) => c.dataset.value)).toEqual(["claude", "codex"]);
  expect(chips("model").map((c) => c.dataset.value)).toEqual(["claude-opus-5", "claude-sonnet-5", "gpt-5.6-sol", "gpt-5.6-terra"]);
  // claude ran opus twice and never ran gpt-5.6-sol; the option list does not shrink, the counts do
  expect(chips("model")[0]).toHaveTextContent("claude-opus-5 2");
  const sol = chips("model")[2]!;
  expect(sol).toHaveTextContent("gpt-5.6-sol 0");
  expect(sol).toHaveAttribute("data-empty", "true");
  expect(sol).toHaveAttribute("aria-pressed", "false");
  expect(sol).not.toBeDisabled();
  // the facet does not filter itself: codex still reports its own three
  expect(chips("harness")[1]).toHaveTextContent("codex 3");
  expect(chips("harness")[0]).toHaveAttribute("aria-pressed", "true");
});

test("a chip click writes the value into the URL, in place, and clicking it again removes it", () => {
  at("?sort=turns&dir=desc&theme=dark");
  mount(sweep());
  const before = history.length;
  fireEvent.click(chips("harness")[0]!);
  expect(location.search).toContain("harness=claude");
  // the neighbouring controls' state survives, and the entry is replaced rather than pushed
  expect(location.search).toContain("sort=turns&dir=desc");
  expect(location.search).toContain("theme=dark");
  expect(history.length).toBe(before);
  fireEvent.click(chips("harness")[0]!);
  // the last value of a facet drops the param: the URL is byte-identical to the unfiltered form
  expect(location.search).toBe("?sort=turns&dir=desc&theme=dark");
});

test("a second value of the same facet is added, comma-separated", () => {
  at("?harness=claude");
  mount(sweep());
  fireEvent.click(chips("harness")[1]!);
  expect(location.search).toBe("?harness=claude,codex");
});

test("a facet with one value says so; a facet with none renders no row", () => {
  mount([cell({ session_id: "1" }), cell({ session_id: "2" })]);
  // all three facets have a single value in this two-cell sweep, and each says so
  expect(screen.getAllByText("only value in this sweep")).toHaveLength(3);
  expect(document.querySelector("[data-facet='skill']")).toBeInTheDocument();
  // ...and it stays clickable: the note is a fact, not a behavioural branch
  expect(chips("skill")[0]).not.toBeDisabled();
  cleanup();

  mount([cell({ session_id: "3", skill: null })]);
  expect(document.querySelector("[data-facet='skill']")).toBeNull();
  expect(document.querySelector("[data-facet='harness']")).toBeInTheDocument();
});

test("a selected value the sweep does not contain still renders as a chip", () => {
  // A stale deeplink is a state `route.ts` deliberately round-trips. Without the union it
  // produced the one thing this bar exists to prevent: "0 of 24 sessions" and a clear button,
  // every chip unlit, and nothing on screen naming what was filtering.
  at("?skill=__gone__");
  mount(sweep());
  const gone = chips("skill").at(-1)!;
  expect(gone.dataset.value).toBe("__gone__");
  expect(gone).toHaveAttribute("data-on", "true");
  expect(gone).toHaveAttribute("data-empty", "true");
  expect(gone).toHaveTextContent("__gone__ 0");
  // ...at the end: the sweep's own options never move because a stale one is present
  expect(chips("skill").map((c) => c.dataset.value)).toEqual(["discovery", "mermaidjs-diagrams", "__gone__"]);
  // and it is the way out — clicking it deselects
  fireEvent.click(gone);
  expect(location.search).toBe("");
});

test("the count is a live region, so a chip toggle announces the new N of M", () => {
  mount(sweep());
  const count = document.getElementById("OverviewFilterCount")!;
  // a chip toggle otherwise announced only its own `aria-pressed`; the outcome was silent
  expect(count).toHaveAttribute("role", "status");
  expect(count).toHaveAttribute("aria-atomic", "true");
  // the live copy, not the hidden sizer beside it
  const live = () => count.querySelector("span:not(.sizer)")!;
  expect(live()).toHaveTextContent(/^6 sessions$/);
  fireEvent.click(chips("harness")[0]!);
  expect(live()).toHaveTextContent(/^3 of 6 sessions$/);
});

test("clearing hands focus to the first chip rather than dropping it on the body", () => {
  at("?harness=claude");
  mount(sweep());
  const clear = document.getElementById("OverviewFiltersClear")!;
  clear.focus();
  fireEvent.click(clear);
  // the button hides itself on its own activation; without the hand-off the reader is dumped at
  // the top of the document and has to tab back in through the whole page header
  expect(document.activeElement).toBe(chips("skill")[0]);
  expect(document.activeElement).not.toBe(document.body);
});

test("the clear control keeps its box when idle, and preserves sort and theme when used", () => {
  mount(sweep());
  // Present, and reserving its 102x28 box: mounting it on the first chip click grew the bar by
  // 21px and slid every facet row — the clicked chip included — out from under the pointer.
  const idle = document.getElementById("OverviewFiltersClear")!;
  expect(idle).toBeInTheDocument();
  // ...and out of the a11y tree and the tab order while it would do nothing.
  expect(idle).toHaveAttribute("aria-hidden", "true");
  expect(idle.tabIndex).toBe(-1);
  cleanup();

  at("?sort=turns&dir=desc&skill=discovery&harness=claude&theme=dark");
  mount(sweep());
  const clear = document.getElementById("OverviewFiltersClear")!;
  expect(clear).not.toHaveAttribute("aria-hidden");
  expect(clear.tabIndex).toBe(0);
  fireEvent.click(clear);
  expect(location.search).toBe("?sort=turns&dir=desc&theme=dark");
});

test("the count reserves the widest sentence it can ever hold, so a filter cannot re-flow the bar", () => {
  mount(sweep());
  const count = document.getElementById("OverviewFilterCount")!;
  const sizer = count.querySelector(".sizer")!;
  // `M of M sessions` is wider than any live value, and is never read out or shown
  expect(sizer).toHaveTextContent("6 of 6 sessions");
  expect(sizer).toHaveAttribute("aria-hidden");
});
