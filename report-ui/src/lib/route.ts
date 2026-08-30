/**
 * Full-URL routing on the History API — no fragment router. Every interactive state of the
 * SPA is addressable as a real query-string URL, which is what makes the e2e permutation
 * matrix (lib/permutations.ts) and "send someone exactly what I see" work:
 *
 *   report.html                                SweepOverview
 *   report.html?sort=<column>&dir=asc|desc     overview, SessionTable sorted
 *   &ssort=<column>&sdir=asc|desc              overview, SessionSummaryTable sorted
 *   report.html?session=<id>                   SessionView
 *   &turn=<n>&view=summary|detailed            which turn is open, how the turn table shows
 *   &axis=turn|line                            x-axis of the per-turn charts (ADR 0025)
 *   &rec=nice|raw                              how records render
 *   &line=<log line>                           scroll to that record, its turn opened
 *   report.html?skill=<a>[,<b>]                overview, only those skills (absent = every skill)
 *   &harness=<a>[,<b>]                         overview, only those harnesses
 *   &model=<a>[,<b>]                           overview, only those models
 *   &theme=light|dark                          forced theme (any route; otherwise remembered)
 *
 * Query strings — not path segments — because the shipped page is one static file copied
 * beside the captured JSON (ADR 0020): it must route with zero server rewrites and over
 * `file://`. Navigations push real history entries; back/forward work; a legacy
 * `#session=…` fragment link parses and is upgraded to its query form on load.
 *
 * A new param added here must be enumerated in `lib/permutations.ts` in the same change, or
 * the matrix silently stops covering it.
 */
import { useEffect, useState } from "react";
import type { AxisMode } from "./series";

export type TurnView = "summary" | "detailed";
export type RecordView = "nice" | "raw";
export type ThemeParam = "light" | "dark";
export type SortDir = "asc" | "desc";

/**
 * The overview's filter selection, one field per facet (ADR 0042). `null` is "every value" —
 * what an absent (or present-but-empty) param means — and a list is "only these": OR within a
 * facet, AND across facets. Always an object, never null, so no consumer null-checks the
 * container.
 */
export interface FacetSelection {
  skill: string[] | null;
  harness: string[] | null;
  model: string[] | null;
}

/** Nothing selected: the unfiltered overview, and what a non-overview route reports. */
export const NO_FACETS: FacetSelection = Object.freeze({ skill: null, harness: null, model: null });

/** The three params, in the order they serialise; `lib/facets.ts` re-declares them as its vocabulary. */
const FACET_PARAMS = ["skill", "harness", "model"] as const;

export interface SortState {
  key: string;
  dir: SortDir;
}

export interface OverviewRoute {
  view: "overview";
  /** `SessionTable`'s column order; null is its own default (`at`, descending). */
  sort: SortState | null;
  /**
   * `SessionSummaryTable`'s column order, on its own param pair. The two tables sort
   * independently — one is the other rolled up, and a reader ranks groups by mean cost while
   * ranking sessions by when they ran — so a shared pair would have made every summary click
   * silently reorder the table below it, and no single URL could express the pair of orders
   * the reader is actually looking at. Null is the fixed skill|case|harness|model key order,
   * which is the only order in which the table's banding and repeat-muting tell the truth.
   */
  summarySort: SortState | null;
  facets: FacetSelection;
  theme: ThemeParam | null;
}

export interface SessionRoute {
  view: "session";
  sessionId: string;
  turn: number | null;
  turnView: TurnView | null;
  axis: AxisMode | null;
  rec: RecordView | null;
  /** A session-log line to scroll to and highlight; its owning turn opens automatically. */
  line: number | null;
  theme: ThemeParam | null;
}

export type Route = OverviewRoute | SessionRoute;

/**
 * A comma-separated facet param as a list: split, trimmed, empties dropped, deduped first-wins.
 * Absent or empty is `null` — every value — so `?skill=` never means "no skill at all", and a
 * value the data does not contain is kept, so a stale deeplink round-trips and matches nothing.
 */
const list = (raw: string | null): string[] | null => {
  const values = [
    ...new Set(
      (raw ?? "")
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean),
    ),
  ];
  return values.length ? values : null;
};

const oneOf = <T extends string>(value: string | null, allowed: readonly T[]): T | null =>
  (allowed as readonly string[]).includes(value ?? "") ? (value as T) : null;

/** A `<param>`/`<param>dir` pair as a sort: the key is what makes it a sort, so a lone `dir` is nothing. */
const sortState = (key: string | null, dir: string | null): SortState | null => (key ? { key, dir: oneOf(dir, ["asc", "desc"]) ?? "asc" } : null);

/** Parse a query string (`?a=b`), or a legacy `#a=b` fragment — the params are the same. */
export function parseSearch(search: string): Route {
  const params = new URLSearchParams(search.replace(/^[?#]/, ""));
  const theme = oneOf(params.get("theme"), ["light", "dark"]);
  const sessionId = params.get("session");
  if (!sessionId) {
    const facets: FacetSelection = { skill: list(params.get("skill")), harness: list(params.get("harness")), model: list(params.get("model")) };
    return {
      view: "overview",
      sort: sortState(params.get("sort"), params.get("dir")),
      summarySort: sortState(params.get("ssort"), params.get("sdir")),
      facets,
      theme,
    };
  }
  const turn = params.get("turn");
  const line = params.get("line");
  return {
    view: "session",
    sessionId,
    turn: turn && /^\d+$/.test(turn) ? Number(turn) : null,
    turnView: oneOf(params.get("view"), ["summary", "detailed"]),
    axis: oneOf(params.get("axis"), ["turn", "line"]),
    rec: oneOf(params.get("rec"), ["nice", "raw"]),
    line: line && /^\d+$/.test(line) ? Number(line) : null,
    theme,
  };
}

/** The current location as a Route; a legacy fragment wins only when the query carries nothing. */
function parseLocation(): Route {
  if (typeof location === "undefined") return { view: "overview", sort: null, summarySort: null, facets: NO_FACETS, theme: null };
  if (!location.search.replace(/^\?$/, "") && location.hash.length > 1) return parseSearch(location.hash);
  return parseSearch(location.search);
}

export interface SessionSearchExtras {
  axis?: AxisMode | null;
  rec?: RecordView | null;
  line?: number | null;
  theme?: ThemeParam | null;
}

/** Param order is fixed so a state always serialises to the same URL (and the same slug). */
export function sessionSearch(sessionId: string, turn?: number | null, turnView?: TurnView | null, extras: SessionSearchExtras = {}): string {
  const params = new URLSearchParams({ session: sessionId });
  if (turn != null) params.set("turn", String(turn));
  if (turnView) params.set("view", turnView);
  if (extras.axis) params.set("axis", extras.axis);
  if (extras.rec) params.set("rec", extras.rec);
  if (extras.line != null) params.set("line", String(extras.line));
  if (extras.theme) params.set("theme", extras.theme);
  return `?${params}`;
}

/**
 * `facets` is last in the argument list on purpose: the two positional call sites that predate
 * it (`overviewSearch({…}, "desc")`, `overviewSearch(null, "dark")`) are untouched, and an
 * unfiltered overview still serialises to the byte-identical URL it always did. Emission order
 * is fixed and independent of argument order.
 */
export function overviewSearch(sort?: SortState | null, theme?: ThemeParam | null, facets?: FacetSelection | null, summarySort?: SortState | null): string {
  const params = new URLSearchParams();
  if (sort) {
    params.set("sort", sort.key);
    params.set("dir", sort.dir);
  }
  if (summarySort) {
    params.set("ssort", summarySort.key);
    params.set("sdir", summarySort.dir);
  }
  for (const facet of FACET_PARAMS) {
    const values = facets?.[facet];
    if (values?.length) params.set(facet, values.join(","));
  }
  if (theme) params.set("theme", theme);
  // `URLSearchParams.toString()` percent-encodes `,` as `%2C`. A comma is a legal sub-delim and
  // these URLs are read, quoted and pasted by humans, so the literal is written back; both forms
  // decode identically on the way in, so the round-trip is unaffected.
  const s = params.toString().replace(/%2C/g, ",");
  return s ? `?${s}` : "?";
}

/** The reader's overview state; a session route contributes only the theme it carries. */
export const asOverview = (route: Route): OverviewRoute =>
  route.view === "overview" ? route : { view: "overview", sort: null, summarySort: null, facets: NO_FACETS, theme: route.theme };

/**
 * The overview route with one thing changed and every sibling param carried through.
 *
 * Every control on the overview writes through this. Spelling the whole route out at each call
 * site is how `sort` came to be dropped by the filter chips and `facets` by the sort heads —
 * the params only ever grow, and a control cannot know about the one added after it. Here the
 * compiler catches the omission once, in one place, instead of the reader catching it as a
 * filter that silently clears itself on a sort click.
 */
export const overviewWith = (route: Route, patch: Partial<Omit<OverviewRoute, "view">>): OverviewRoute => ({ ...asOverview(route), ...patch });

/** The route rebuilt as its canonical query string; the one writer every control uses. */
export function routeSearch(route: Route): string {
  if (route.view === "overview") return overviewSearch(route.sort, route.theme, route.facets, route.summarySort);
  return sessionSearch(route.sessionId, route.turn, route.turnView, route);
}

const ROUTE_EVENT = "xh-route";

const commit = (route: Route, mode: "push" | "replace"): void => {
  // pathname + search rebuilt explicitly, so a lingering legacy fragment is always dropped
  const url = location.pathname + routeSearch(route);
  if (mode === "push") history.pushState(null, "", url);
  else history.replaceState(null, "", url);
  dispatchEvent(new Event(ROUTE_EVENT));
};

/** Navigate: a real history entry, so back/forward walk the pages the reader visited. */
export const pushRoute = (route: Route): void => commit(route, "push");

/** Rewrite the current entry in place: for controls refining the state the reader is already on. */
export const replaceRoute = (route: Route): void => commit(route, "replace");

/** Left-click intercept for `<a href="?…">`: SPA navigation, while the real href keeps middle-click and copy-link honest. */
export function navigateOnClick(search: string): (e: { preventDefault: () => void; metaKey?: boolean; ctrlKey?: boolean; button?: number }) => void {
  return (e) => {
    if (e.metaKey || e.ctrlKey || (e.button ?? 0) !== 0) return;
    e.preventDefault();
    pushRoute(parseSearch(search));
  };
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(parseLocation);
  useEffect(() => {
    // A legacy fragment deeplink is upgraded to its canonical query URL once, on load.
    if (typeof location !== "undefined" && location.hash.length > 1 && !location.search.replace(/^\?$/, "")) {
      history.replaceState(null, "", location.pathname + routeSearch(parseSearch(location.hash)));
    }
    const onChange = () => setRoute(parseLocation());
    addEventListener("popstate", onChange);
    addEventListener(ROUTE_EVENT, onChange);
    return () => {
      removeEventListener("popstate", onChange);
      removeEventListener(ROUTE_EVENT, onChange);
    };
  }, []);
  return route;
}
