import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { ChartAxisToggle, ContextWindowChart, OutputPerTurnChart, TokenWaterfallChart, TurnTiersChart } from "@/components/charts";
import { CopyId } from "@/components/CopyId";
import { El } from "@/components/El";
import {
  CostByTierPanel,
  FinalMessagePanel,
  ReconciliationPanel,
  RecordKindsPanel,
  SessionTurnTable,
  SkillCoveragePanel,
  type SkillCoverage,
  type TurnView,
} from "@/components/panels";
import { RecordViewToggle, TurnRawRecords, turnId, type RecordView } from "@/components/records";
import { VerdictBadge } from "@/components/VerdictBadge";
import { useLog } from "@/hooks/useLog";
import { useResult } from "@/hooks/useResult";
import { fmt, pct, secs, usd, when, windowLabel } from "@/lib/format";
import { sessionHash } from "@/lib/route";
import type { AxisMode } from "@/lib/series";
import type { Cell } from "@/lib/types";

interface Props {
  cell: Cell | undefined;
  sessionId: string;
  turn: number | null;
  turnView: TurnView | null;
}

/** One captured session: metadata, the per-turn charts, the panels, the turn table and its records (glossary: `SessionView`). */
export function SessionView({ cell, sessionId, turn, turnView }: Props) {
  const { result, error } = useResult(cell);
  const { lines } = useLog(cell);
  const [axis, setAxis] = useState<AxisMode>("turn");
  const [view, setView] = useState<TurnView>(turnView ?? "summary");
  const [openTurn, setOpenTurn] = useState<number | null>(turn);
  const [recordView, setRecordView] = useState<RecordView>("nice");

  // The hash is the source of truth for which turn is open and which view is shown: when the
  // route changes, the local state resets to it (state derived from props, reset during render).
  const [seen, setSeen] = useState({ turn, turnView });
  if (seen.turn !== turn || seen.turnView !== turnView) {
    setSeen({ turn, turnView });
    setOpenTurn(turn);
    if (turnView) setView(turnView);
  }

  // Scroll to the opened turn once its details row (and the log it renders) exist.
  useEffect(() => {
    if (openTurn == null || !cell || !lines) return;
    const el = document.getElementById(turnId(cell.session_id, openTurn));
    if (el && typeof el.scrollIntoView === "function") el.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [openTurn, cell, lines, result]);

  if (!cell) {
    return (
      <section id="SessionView" className="space-y-4" data-el="SessionView">
        <p className="text-destructive">
          No captured session <code>{sessionId}</code> in this index.
        </p>
        <Button asChild variant="outline">
          <a href="#">← all sessions</a>
        </Button>
      </section>
    );
  }

  const rows: [string, React.ReactNode][] = [
    ["verdict", <VerdictBadge key="v" verdict={cell.verdict} />],
    ["suite", <code key="s">{cell.suite ?? "–"}</code>],
    ["case", cell.case],
    ["skill", cell.skill ?? "–"],
    ["fixture", cell.fixture ?? "–"],
    [
      "prompt",
      cell.prompt ? (
        <span key="p" className="whitespace-pre-wrap">
          {cell.prompt}
        </span>
      ) : (
        "not recorded on this result; replay to recover it (ADR 0025)"
      ),
    ],
    ["harness / model", `${cell.harness} / ${cell.model}`],
    ["started", when(cell.at)],
    ["wall", secs(cell.wall_ms)],
    ["estimated_cost_usd", usd(cell.estimated_cost_usd)],
    ["harness_reported_cost_usd", usd(cell.harness_reported_cost_usd)],
    ["accumulative_billed_tokens", fmt(cell.accumulative_billed_tokens)],
    ["baseline_tokens", fmt(cell.baseline_tokens)],
    ["peak_context_tokens", `${fmt(cell.peak_context_tokens)} · ${pct(cell.context_window_pct)} of ${windowLabel(cell.context_window)}`],
    ["context window", cell.context_window ? `${fmt(cell.context_window)} tokens (harness-reported)` : "not reported"],
    ["turns", `${fmt(cell.turns)}${cell.reported_turns != null ? ` (harness reported ${fmt(cell.reported_turns)})` : ""}`],
    ["tool_calls", fmt(cell.tool_calls)],
    ["files written", cell.files_written.length ? cell.files_written.join(", ") : "none"],
  ];

  const changeView = (v: TurnView) => {
    setView(v);
    history.replaceState(null, "", sessionHash(cell.session_id, openTurn, v));
  };
  const changeOpenTurn = (n: number | null) => {
    setOpenTurn(n);
    history.replaceState(null, "", sessionHash(cell.session_id, n, view));
  };

  return (
    <section id="SessionView" className="space-y-4" data-el="SessionView">
      <header id="SessionHeader" className="flex flex-wrap items-center gap-3">
        <Button asChild variant="ghost" size="sm">
          <a href="#">← all sessions</a>
        </Button>
        <h2 id="SessionTitle" className="text-base font-semibold">
          {cell.case} · {cell.harness}/{cell.model} <CopyId id={cell.session_id} />
          <El name="SessionView" />
        </h2>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>
            Session metadata
            <El name="SessionMetaTable" />
          </CardTitle>
          {error ? <CardDescription className="text-destructive">{error}</CardDescription> : null}
        </CardHeader>
        <CardContent>
          <Table id="SessionMetaTable" className="text-sm">
            <TableBody>
              {rows.map(([k, v]) => (
                <TableRow key={k}>
                  <TableCell className="text-muted-foreground w-56 font-mono text-xs">{k}</TableCell>
                  <TableCell>{v}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {result ? (
        <>
          <ChartAxisToggle mode={axis} onChange={setAxis} />
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <Card className="xl:col-span-2">
              <CardContent>
                <TokenWaterfallChart result={result} lines={lines} mode={axis} />
              </CardContent>
            </Card>
            <Card className="xl:col-span-2">
              <CardContent>
                <ContextWindowChart result={result} lines={lines} mode={axis} />
              </CardContent>
            </Card>
            <ReconciliationPanel result={result} />
            <CostByTierPanel result={result} />
            <Card>
              <CardContent>
                <OutputPerTurnChart result={result} lines={lines} mode={axis} />
              </CardContent>
            </Card>
            <Card>
              <CardContent>
                <TurnTiersChart result={result} lines={lines} mode={axis} />
              </CardContent>
            </Card>
            <div className="xl:col-span-2">
              <SkillCoveragePanel coverage={result.skill_coverage as unknown as SkillCoverage} />
            </div>
            <div className="xl:col-span-2">
              <RecordKindsPanel recordKinds={result.record_kinds} />
            </div>
          </div>
          <SessionTurnTable
            result={result}
            cell={cell}
            view={view}
            onViewChange={changeView}
            openTurn={openTurn}
            onOpenTurn={changeOpenTurn}
            recordView={recordView}
            onRecordViewChange={setRecordView}
            toolbarExtra={<RecordViewToggle view={recordView} onChange={setRecordView} />}
            renderTurnRecords={(call) => <TurnRawRecords result={result} call={call} lines={lines} view={recordView} />}
          />
          <FinalMessagePanel text={result.final_text} />
        </>
      ) : error ? null : (
        <p className="text-muted-foreground">loading result…</p>
      )}
    </section>
  );
}
