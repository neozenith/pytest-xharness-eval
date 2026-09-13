/**
 * `SessionView`'s composition of the two loads, which no component test below it can see:
 * the spawned threads' transcripts arrive in a *second* pass, after the result that names
 * them, and the view has to declare that it is still loading during it. Without that
 * declaration the e2e `settle()` helper — `__XH_PENDING__ === 0`, view mounted, no
 * `[data-xh-loading]` — can return in the gap between the result rendering and the
 * transcript fetches starting, and every screenshot of a spawning session is a race.
 */
import { act, waitFor } from "@testing-library/react";
import { renderT as render } from "./render";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SessionView } from "@/views/SessionView";
import * as data from "@/lib/data";
import type { Cell, RunResult } from "@/lib/types";
import type { SessionRoute as Route } from "@/lib/route";

vi.mock("plotly.js-basic-dist-min", () => ({ default: { react: vi.fn(), purge: vi.fn() } }));

const route: Route = {
  view: "session",
  sessionId: "sid1",
  turn: null,
  turnView: null,
  axis: null,
  rec: null,
  line: null,
  subTurn: null,
  subLine: null,
  theme: null,
};

const cell = { session_id: "sid1", case: "eval_x", harness: "claude", model: "m", result: "sid1/result.json", files_written: [] } as unknown as Cell;

const result = (subagents: unknown[]): RunResult =>
  ({
    harness: "claude",
    model: "m",
    session_id: "sid1",
    calls: [],
    usage: {},
    rates_applied: {},
    final_text: "",
    files_written: [],
    tool_calls: {},
    record_kinds: {},
    skill_coverage: {},
    case: {},
    subagents,
  }) as unknown as RunResult;

const loading = () => document.querySelectorAll("[data-xh-loading]").length;

afterEach(() => vi.restoreAllMocks());

test("a spawning session keeps declaring itself loading until the transcripts arrive, not just until the result does", async () => {
  let releaseTranscript: (text: string) => void = () => {};
  vi.spyOn(data, "loadResult").mockResolvedValue(result([{ id: "a", agent: "Explore", log: "subagents/a.jsonl", calls: [], usage: {} }]));
  vi.spyOn(data, "loadLog").mockResolvedValue("");
  vi.spyOn(data, "loadSubagentLog").mockImplementation(() => new Promise<string>((r) => (releaseTranscript = r)));

  await act(async () => {
    render(
      <TooltipProvider>
        <SessionView cell={cell} route={route} />
      </TooltipProvider>,
    );
  });
  /*
   * The result and the session log have both settled here — the old `data-xh-loading="result"`
   * is gone — and this is exactly the moment settle() would have returned. The transcripts have
   * not arrived, so the view must still say so.
   */
  expect(document.querySelector("[data-xh-loading='result']")).toBeNull();
  expect(document.querySelector("[data-xh-loading='subagents']")).not.toBeNull();

  await act(async () => releaseTranscript("{}\n"));
  await waitFor(() => expect(loading()).toBe(0));
});

test("a session that spawned nothing never declares a transcript load it will not do", async () => {
  vi.spyOn(data, "loadResult").mockResolvedValue(result([]));
  vi.spyOn(data, "loadLog").mockResolvedValue("");
  const load = vi.spyOn(data, "loadSubagentLog");
  await act(async () => {
    render(
      <TooltipProvider>
        <SessionView cell={cell} route={route} />
      </TooltipProvider>,
    );
  });
  // no marker to hang settle() on, and no fetch attempted
  await waitFor(() => expect(loading()).toBe(0));
  expect(load).not.toHaveBeenCalled();
});
