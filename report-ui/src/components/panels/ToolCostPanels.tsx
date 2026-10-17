/**
 * When each tool call ran, how long it took and what it cost, and the same for the skill under
 * test (ADR 0073). Python attributes every figure (`derive/toolcost.py`); these panels only print.
 *
 * A tool call has two costs. `issuing_cost_usd` is the model call that asked for it, split across
 * the tools that call issued. `context_cost_usd` is what carrying its result cost: its share of
 * every later prompt that held it, listed turn by turn in its trace, with `c` marking a turn that
 * re-read it from the prompt cache.
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { El } from "@/components/El";
import { fmt, NONE, short, usd } from "@/lib/format";
import type { RunResult, SkillUse, ToolCharge, ToolCost } from "@/lib/types";
import { clock, ms } from "./helpers";
import { KvTable } from "./shared";

const threadLabel = (thread: string): string => (thread ? short(thread) : "primary");

const traceText = (trace: ToolCharge[]): string => trace.map((c) => `t${c.turn}${c.cached ? "c" : ""} ${usd(c.usd)}`).join(" · ");

/** The trace behind a context cost, folded away until asked for: it can run to every later turn. */
function Trace({ trace }: { trace: ToolCharge[] }) {
  if (!trace.length) return <span className="muted">{NONE}</span>;
  return (
    <details data-el="ToolCostTrace">
      <summary>
        {trace.length} turn{trace.length === 1 ? "" : "s"}
      </summary>
      <span className="num" style={{ fontSize: 12 }}>
        {traceText(trace)}
      </span>
    </details>
  );
}

/** ToolCostTable: one row per tool call of every thread, in ledger order. */
export function ToolCostTable({ result }: { result: RunResult }) {
  const costs: ToolCost[] = result.tool_costs ?? [];
  return (
    <Card id="ToolCostPanel" data-el="ToolCostTable">
      <CardHeader>
        <CardTitle>
          Tool calls
          <El name="ToolCostTable" />
        </CardTitle>
      </CardHeader>
      <CardContent>
        {result.tool_costs == null ? (
          <span className="warn">This result predates ADR 0073: replay the cache to time and price its tool calls.</span>
        ) : !costs.length ? (
          <span className="muted">This session issued no tool calls.</span>
        ) : (
          <Table id="ToolCostTable" scrollLabel="tool calls">
            <TableHeader>
              <TableRow>
                <TableHead>thread</TableHead>
                <TableHead>turn</TableHead>
                <TableHead>tool</TableHead>
                <TableHead>started</TableHead>
                <TableHead className="num">duration_ms</TableHead>
                <TableHead className="num" title="the issuing call's cost over the tools it issued">
                  issuing_cost_usd
                </TableHead>
                <TableHead className="num" title="estimated tokens the result added to the context">
                  result_tokens
                </TableHead>
                <TableHead className="num" title="the result's share of every later prompt that carried it">
                  context_cost_usd
                </TableHead>
                <TableHead className="num" title="later calls that re-read the result from the prompt cache">
                  cache_rereads
                </TableHead>
                <TableHead>trace</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {costs.map((c) => (
                <TableRow key={`${c.thread}/${c.id}/${c.turn}`} data-el="ToolCostRow" data-tool={c.name}>
                  <TableCell>{threadLabel(c.thread)}</TableCell>
                  <TableCell className="num">{c.turn}</TableCell>
                  <TableCell title={c.summary}>
                    <code className="code-chip">{c.name}</code>
                  </TableCell>
                  <TableCell className="num">{clock(c.started_at)}</TableCell>
                  <TableCell className="num">{ms(c.duration_ms)}</TableCell>
                  <TableCell className="num">{usd(c.issuing_cost_usd)}</TableCell>
                  <TableCell className="num">{fmt(c.result_tokens)}</TableCell>
                  <TableCell className="num">{usd(c.context_cost_usd)}</TableCell>
                  <TableCell className="num">{fmt(c.cache_rereads)}</TableCell>
                  <TableCell>
                    <Trace trace={c.trace} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

const isUse = (use: RunResult["skill_use"]): use is SkillUse => Boolean(use && "skill" in use);

/** SkillUsePanel: the skill's span and totals, then every access with its tool call's figures. */
export function SkillUsePanel({ result }: { result: RunResult }) {
  const use = result.skill_use;
  return (
    <Card id="SkillUsePanel" data-el="SkillUsePanel">
      <CardHeader>
        <CardTitle>
          Skill use
          <El name="SkillUsePanel" />
        </CardTitle>
      </CardHeader>
      <CardContent>
        {use == null ? (
          <span className="warn">This result predates ADR 0073: replay the cache to trace its skill use.</span>
        ) : !isUse(use) ? (
          <span className="muted">The skill was never triggered: no invocation named it and no tool call touched its files.</span>
        ) : (
          <>
            <KvTable
              id="SkillUseSpan"
              label="skill use"
              rows={[
                ["skill", <code key="s">{use.skill}</code>],
                ["trigger", use.trigger],
                ["triggered", `turn ${use.triggered_turn} · ${clock(use.triggered_at)}`],
                ["last used", `turn ${use.last_turn} · ${clock(use.last_at)}`],
                ["duration_ms", ms(use.duration_ms)],
                ["tool_calls", fmt(use.tool_calls)],
                ["issuing_cost_usd", usd(use.issuing_cost_usd)],
                ["context_cost_usd", usd(use.context_cost_usd)],
                ["cache_rereads", fmt(use.cache_rereads)],
              ]}
            />
            {use.events.length ? (
              <Table id="SkillUseEvents" scrollLabel="skill file accesses">
                <TableHeader>
                  <TableRow>
                    <TableHead>turn</TableHead>
                    <TableHead>thread</TableHead>
                    <TableHead>tool</TableHead>
                    <TableHead>file</TableHead>
                    <TableHead>access</TableHead>
                    <TableHead className="num">duration_ms</TableHead>
                    <TableHead className="num">issuing_cost_usd</TableHead>
                    <TableHead className="num">context_cost_usd</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {use.events.map((e, i) => (
                    <TableRow key={i} data-el="SkillUseEvent" data-access={e.access}>
                      <TableCell className="num">{e.turn}</TableCell>
                      <TableCell>{threadLabel(e.thread)}</TableCell>
                      <TableCell>
                        <code className="code-chip">{e.tool}</code>
                      </TableCell>
                      <TableCell>
                        <code>{e.path}</code>
                      </TableCell>
                      <TableCell>{e.access}</TableCell>
                      <TableCell className="num">{ms(e.duration_ms)}</TableCell>
                      <TableCell className="num">{usd(e.issuing_cost_usd)}</TableCell>
                      <TableCell className="num">{usd(e.context_cost_usd)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : null}
            <span className="muted" style={{ fontSize: 12 }}>
              An access shows its tool call's figures, so a call that touched two files appears twice; the totals count each call once.
            </span>
          </>
        )}
      </CardContent>
    </Card>
  );
}
