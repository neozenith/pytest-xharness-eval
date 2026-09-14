/**
 * `useSubagentLogs`: every spawned thread's transcript, or `null` until they have all
 * settled. The guarantees under test are the ones a band relies on and a comment cannot
 * prove — the map never appears half-built, a load that belongs to a session the reader has
 * left cannot land on the one they are on, and a thread whose transcript failed is *in* the
 * map with its error rather than missing from it (missing would read as "still loading").
 */
import { act, render, waitFor } from "@testing-library/react";
import { useSubagentLogs } from "@/hooks/useSubagentLogs";
import * as data from "@/lib/data";
import type { Cell, RunResult, Subagent } from "@/lib/types";

const cell = (id = "sid1"): Cell => ({ session_id: id, result: `${id}/result.json` }) as Cell;
const sub = (id: string): Subagent => ({ id, agent: "Explore", log: `subagents/${id}.jsonl`, calls: [] }) as unknown as Subagent;
const runResult = (...ids: string[]): RunResult => ({ subagents: ids.map(sub) }) as unknown as RunResult;

/** Renders the hook and exposes what it returned on the latest render. */
function Probe({ cell: c, result }: { cell: Cell | undefined; result: RunResult | null }) {
  const logs = useSubagentLogs(c, result);
  return <div data-testid="out">{logs == null ? "loading" : [...logs].map(([k, v]) => `${k}=${v.error ?? v.lines.join("|")}`).join(",")}</div>;
}

afterEach(() => vi.restoreAllMocks());

test("null until every transcript has settled, then one map holding all of them", async () => {
  const gate: ((text: string) => void)[] = [];
  vi.spyOn(data, "loadSubagentLog").mockImplementation(() => new Promise<string>((resolve) => gate.push(resolve)));
  const { getByTestId } = render(<Probe cell={cell()} result={runResult("a", "b")} />);
  expect(getByTestId("out")).toHaveTextContent("loading");
  // one of two settled is still "loading": a half-built map would make a band claim the
  // other thread has no records at all
  await act(async () => gate[0]!("one\n"));
  expect(getByTestId("out")).toHaveTextContent("loading");
  await act(async () => gate[1]!("two\n"));
  await waitFor(() => expect(getByTestId("out")).toHaveTextContent("a=one,b=two"));
});

test("a thread whose transcript could not be read is in the map with its error", async () => {
  vi.spyOn(data, "loadSubagentLog").mockImplementation((_c, s) => (s.id === "bad" ? Promise.reject(new Error("HTTP 404")) : Promise.resolve("ok\n")));
  const { getByTestId } = render(<Probe cell={cell()} result={runResult("good", "bad")} />);
  await waitFor(() => expect(getByTestId("out")).toHaveTextContent("good=ok"));
  // present, and carrying why — not absent, which the caller reads as "still loading"
  expect(getByTestId("out")).toHaveTextContent("bad=Error: HTTP 404");
});

test("a session that spawned nothing resolves to an empty map, never to a permanent null", async () => {
  const { getByTestId } = render(<Probe cell={cell()} result={runResult()} />);
  // this is what clears `data-xh-loading="subagents"`; a permanent null would hang settle()
  await waitFor(() => expect(getByTestId("out")).toHaveTextContent(""));
  expect(getByTestId("out").textContent).toBe("");
});

test("the transcripts of the session the reader left are never shown under the one they are on", async () => {
  const gate = new Map<string, (text: string) => void>();
  vi.spyOn(data, "loadSubagentLog").mockImplementation((_c, s) => new Promise<string>((resolve) => gate.set(s.id, resolve)));
  const { getByTestId, rerender } = render(<Probe cell={cell("sid1")} result={runResult("old")} />);
  await act(async () => gate.get("old")!("STALE\n"));
  await waitFor(() => expect(getByTestId("out")).toHaveTextContent("old=STALE"));

  /*
   * The reader navigates. The state still holds sid1's map, and the new session's load has
   * not even been started yet — this render is the whole window, and it is why the hook
   * checks the map it holds against the result it was handed rather than trusting the
   * effect's cleanup. Without that check the band renders the *previous* session's
   * transcript under the new session's threads for a frame.
   */
  rerender(<Probe cell={cell("sid2")} result={runResult("new")} />);
  expect(getByTestId("out")).toHaveTextContent("loading");
  expect(getByTestId("out").textContent).not.toContain("STALE");

  await act(async () => gate.get("new")!("fresh\n"));
  await waitFor(() => expect(getByTestId("out")).toHaveTextContent("new=fresh"));

  // and a load still in flight for the session the reader left cannot land on this one either
  await act(async () => gate.get("old")!("LATE\n"));
  expect(getByTestId("out").textContent).toBe("new=fresh");
});

test("no cell or no result yet is loading, and starts nothing", () => {
  const load = vi.spyOn(data, "loadSubagentLog");
  const { getByTestId } = render(<Probe cell={cell()} result={null} />);
  expect(getByTestId("out")).toHaveTextContent("loading");
  render(<Probe cell={undefined} result={runResult("a")} />);
  expect(load).not.toHaveBeenCalled();
});
