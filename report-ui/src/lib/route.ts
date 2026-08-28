/**
 * Full-URL routing on the History API — no fragment router. Every interactive state of the
 * SPA is addressable as a real query-string URL, which is what makes the e2e permutation
 * matrix (lib/permutations.ts) and "send someone exactly what I see" work:
 *
 *   report.html                                SweepOverview
 *   report.html?sort=<column>&dir=asc|desc     overview, table sorted
 *   report.html?session=<id>                   SessionView
 *   &turn=<n>&view=summary|detailed            which turn is open, how the turn table shows
 *   &axis=turn|line                            x-axis of the per-turn charts (ADR 0025)
 *   &rec=nice|raw                              how records render
 *   &line=<log line>                           scroll to that record, its turn opened
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

export interface OverviewRoute {
  view: "overview";
  sort: { key: string; dir: SortDir } | null;
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

const oneOf = <T extends string>(value: string | null, allowed: readonly T[]): T | null =>
  (allowed as readonly string[]).includes(value ?? "") ? (value as T) : null;

/** Parse a query string (`?a=b`), or a legacy `#a=b` fragment — the params are the same. */
export function parseSearch(search: string): Route {
  const params = new URLSearchParams(search.replace(/^[?#]/, ""));
  const theme = oneOf(params.get("theme"), ["light", "dark"]);
  const sessionId = params.get("session");
  if (!sessionId) {
    const key = params.get("sort");
    const dir = oneOf(params.get("dir"), ["asc", "desc"]);
    return { view: "overview", sort: key ? { key, dir: dir ?? "asc" } : null, theme };
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
  if (typeof location === "undefined") return { view: "overview", sort: null, theme: null };
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

export function overviewSearch(sort?: { key: string; dir: SortDir } | null, theme?: ThemeParam | null): string {
  const params = new URLSearchParams();
  if (sort) {
    params.set("sort", sort.key);
    params.set("dir", sort.dir);
  }
  if (theme) params.set("theme", theme);
  const s = params.toString();
  return s ? `?${s}` : "?";
}

/** The route rebuilt as its canonical query string; the one writer every control uses. */
export function routeSearch(route: Route): string {
  if (route.view === "overview") return overviewSearch(route.sort, route.theme);
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
