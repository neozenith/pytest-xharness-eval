/**
 * Hash routing, unchanged from the first microsite so existing links keep working:
 * `#` or empty -> SweepOverview; `#session=<session_id>[&turn=<n>][&view=summary|detailed]` -> SessionView.
 */
import { useEffect, useState } from "react";

export type TurnView = "summary" | "detailed";

export type Route = { view: "overview" } | { view: "session"; sessionId: string; turn: number | null; turnView: TurnView | null };

export function parseHash(hash: string): Route {
  const params = new URLSearchParams(hash.replace(/^#/, ""));
  const sessionId = params.get("session");
  if (!sessionId) return { view: "overview" };
  const turn = params.get("turn");
  const view = params.get("view");
  return {
    view: "session",
    sessionId,
    turn: turn && /^\d+$/.test(turn) ? Number(turn) : null,
    turnView: view === "summary" || view === "detailed" ? view : null,
  };
}

export function sessionHash(sessionId: string, turn?: number | null, turnView?: TurnView | null): string {
  const params = new URLSearchParams({ session: sessionId });
  if (turn != null) params.set("turn", String(turn));
  if (turnView) params.set("view", turnView);
  return `#${params}`;
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseHash(typeof location === "undefined" ? "" : location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseHash(location.hash));
    addEventListener("hashchange", onChange);
    return () => removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
