/**
 * `lib/data.ts`'s two modes (ADR 0020, ADR 0024): the inline payload when `report.py
 * --inline` embedded one, otherwise a fetch beside the page. A spawned thread's transcript
 * is the accessor with real work to do in each — a key to build, and a path to resolve.
 */
import { loadSubagentLog, subagentLogKey } from "@/lib/data";
import type { Cell, InlineData, Subagent } from "@/lib/types";

const cell = (over: Partial<Cell> = {}): Cell =>
  ({
    session_id: "sid1",
    result: "../results/discovery/claude/claude-opus-5/20260101T000000Z/sid1/result.json",
    log: "../results/discovery/claude/claude-opus-5/20260101T000000Z/sid1/log.jsonl",
    ...over,
  }) as Cell;

const sub = (over: Partial<Subagent> = {}): Subagent => ({ id: "abc", log: "subagents/agent-abc.jsonl", ...over }) as Subagent;

afterEach(() => {
  delete window.__XH_DATA__;
  vi.unstubAllGlobals();
});

test("the inline key qualifies a thread by its session, so two runs of the same agent stay apart", () => {
  expect(subagentLogKey("sid1", "abc")).toBe("sid1/abc");
  expect(subagentLogKey("sid2", "abc")).not.toBe(subagentLogKey("sid1", "abc"));
});

test("inline: a thread's transcript comes out of the payload under its qualified key, never the session's own log", async () => {
  window.__XH_DATA__ = { logs: { sid1: "PRIMARY\n", "sid1/abc": "THREAD\n" } } as unknown as InlineData;
  await expect(loadSubagentLog(cell(), sub())).resolves.toBe("THREAD\n");
  // a thread the payload does not carry is no transcript, not the primary log by accident
  await expect(loadSubagentLog(cell(), sub({ id: "missing" }))).resolves.toBe("");
});

test("served: the transcript path resolves against the session directory, which is where the result sits", async () => {
  const fetched: string[] = [];
  vi.stubGlobal("fetch", (url: string) => {
    fetched.push(url);
    return Promise.resolve({ ok: true, text: () => Promise.resolve("THREAD\n") } as Response);
  });
  await expect(loadSubagentLog(cell(), sub())).resolves.toBe("THREAD\n");
  // the result's own filename is replaced, so the fetch lands beside it — not beside the page
  expect(fetched).toEqual(["../results/discovery/claude/claude-opus-5/20260101T000000Z/sid1/subagents/agent-abc.jsonl"]);
});

test("served: a path that is not evidence in this cache is no transcript, and is never fetched", async () => {
  const fetched: string[] = [];
  vi.stubGlobal("fetch", (url: string) => {
    fetched.push(url);
    return Promise.resolve({ ok: true, text: () => Promise.resolve("LEAKED") } as Response);
  });
  // a result captured before ADR 0033's rewrite still carries the harness's own absolute path
  await expect(loadSubagentLog(cell(), sub({ log: "/Users/me/.claude/projects/x/agent-abc.jsonl" }))).resolves.toBe("");
  // and nothing may climb out of the session directory
  await expect(loadSubagentLog(cell(), sub({ log: "../../../../etc/passwd" }))).resolves.toBe("");
  await expect(loadSubagentLog(cell(), sub({ log: "" }))).resolves.toBe("");
  expect(fetched).toEqual([]);
});

test("served: a transcript the cache does not hold rejects, so the band can say why rather than show empty cards", async () => {
  vi.stubGlobal("fetch", () => Promise.resolve({ ok: false, status: 404 } as Response));
  await expect(loadSubagentLog(cell(), sub())).rejects.toThrow(/404/);
});
