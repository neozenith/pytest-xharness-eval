import { useEffect, useMemo, useState } from "react";
import { Text, View, XStack } from "tamagui";
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
import { navigateOnClick, replaceRoute, type SessionRoute } from "@/lib/route";
import type { AxisMode } from "@/lib/series";
import type { Cell } from "@/lib/types";

interface Props {
  cell: Cell | undefined;
  route: SessionRoute;
}

/** One captured session: metadata, the per-turn charts, the panels, the turn table and its records (glossary: `SessionView`). */
export function SessionView({ cell, route }: Props) {
  const { sessionId } = route;
  const { result, error } = useResult(cell);
  const { lines } = useLog(cell);
  const [axis, setAxis] = useState<AxisMode>(route.axis ?? "turn");
  const [view, setView] = useState<TurnView>(route.turnView ?? "summary");
  const [openTurn, setOpenTurn] = useState<number | null>(route.turn);
  const [recordView, setRecordView] = useState<RecordView>(route.rec ?? "nice");

  // The hash is the source of truth for every control here: when the route changes, the
  // local state resets to it (state derived from props, reset during render).
  const [seen, setSeen] = useState(route);
  if (seen !== route) {
    setSeen(route);
    setOpenTurn(route.turn);
    // an absent param means its default: the hash alone reproduces the whole state
    setView(route.turnView ?? "summary");
    setAxis(route.axis ?? "turn");
    setRecordView(route.rec ?? "nice");
  }

  // Every control writes the whole route back, so a copied URL reproduces exactly this state.
  const write = (next: Partial<SessionRoute>) => {
    replaceRoute({
      view: "session",
      sessionId,
      turn: openTurn,
      turnView: view,
      axis: axis === "turn" ? null : axis,
      rec: recordView === "nice" ? null : recordView,
      line: null,
      theme: route.theme,
      ...next,
    });
  };

  // Scroll to the opened turn once its details row (and the log it renders) exist.
  useEffect(() => {
    if (openTurn == null || route.line != null || !cell || !lines) return;
    const el = document.getElementById(turnId(cell.session_id, openTurn));
    if (el && typeof el.scrollIntoView === "function") el.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [openTurn, route.line, cell, lines, result]);

  // `line=` targets one record: its owning turn opens (derived, not stored), and once the
  // card exists it is scrolled to and flashed.
  const lineOwner = useMemo(
    () => (route.line != null && result ? (result.calls.find((k) => (k.records ?? []).includes(route.line!))?.n ?? null) : null),
    [route.line, result],
  );
  const shownTurn = openTurn ?? lineOwner;
  useEffect(() => {
    if (route.line == null || !result || !lines) return;
    const el = document.getElementById(`L${route.line}`);
    if (!el) return;
    if (typeof el.scrollIntoView === "function") el.scrollIntoView({ block: "center" });
    el.classList.add("xh-target");
    const timer = setTimeout(() => el.classList.remove("xh-target"), 2400);
    return () => clearTimeout(timer);
  }, [route.line, result, lines, shownTurn]);

  if (!cell) {
    return (
      <View render="section" id="SessionView" gap={16} data-el="SessionView">
        <Text render="p" color="$bad" fontFamily="$body" fontSize={14}>
          No captured session <code>{sessionId}</code> in this index.
        </Text>
        <Button render={<a href="?" onClick={navigateOnClick("?")} />} variant="outline">
          ← all sessions
        </Button>
      </View>
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
        <span key="p" style={{ whiteSpace: "pre-wrap" }}>
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
    write({ turnView: v });
  };
  const changeOpenTurn = (n: number | null) => {
    setOpenTurn(n);
    write({ turn: n });
  };
  const changeAxis = (a: AxisMode) => {
    setAxis(a);
    write({ axis: a === "turn" ? null : a });
  };
  const changeRecordView = (r: RecordView) => {
    setRecordView(r);
    write({ rec: r === "nice" ? null : r });
  };

  return (
    <View render="section" id="SessionView" gap={16} data-el="SessionView">
      <XStack render={<header id="SessionHeader" />} flexWrap="wrap" alignItems="center" gap={12}>
        <Button render={<a href="?" onClick={navigateOnClick("?")} />} variant="ghost" size="sm">
          ← all sessions
        </Button>
        <Text render={<h2 id="SessionTitle" />} fontFamily="$body" fontSize={16} fontWeight="600" margin={0}>
          {cell.case} · {cell.harness}/{cell.model} <CopyId id={cell.session_id} />
          <El name="SessionView" />
        </Text>
      </XStack>

      <Card>
        <CardHeader>
          <CardTitle>
            Session metadata
            <El name="SessionMetaTable" />
          </CardTitle>
          {error ? <CardDescription className="text-destructive">{error}</CardDescription> : null}
        </CardHeader>
        <CardContent>
          <Table id="SessionMetaTable">
            <TableBody>
              {rows.map(([k, v]) => (
                <TableRow key={k}>
                  <TableCell className="key">{k}</TableCell>
                  <TableCell style={{ whiteSpace: "normal" }}>{v}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {result ? (
        <>
          <ChartAxisToggle mode={axis} onChange={changeAxis} />
          <View style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(560px, 100%), 1fr))", gap: 16 }}>
            <View style={{ gridColumn: "1 / -1" }}>
              <Card>
                <CardContent>
                  <TokenWaterfallChart result={result} lines={lines} mode={axis} />
                </CardContent>
              </Card>
            </View>
            <View style={{ gridColumn: "1 / -1" }}>
              <Card>
                <CardContent>
                  <ContextWindowChart result={result} lines={lines} mode={axis} />
                </CardContent>
              </Card>
            </View>
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
            <ReconciliationPanel result={result} />
            <CostByTierPanel result={result} />
            <View style={{ gridColumn: "1 / -1" }}>
              <SkillCoveragePanel coverage={result.skill_coverage as unknown as SkillCoverage} />
            </View>
            <View style={{ gridColumn: "1 / -1" }}>
              <RecordKindsPanel recordKinds={result.record_kinds} />
            </View>
          </View>
          <SessionTurnTable
            result={result}
            view={view}
            onViewChange={changeView}
            openTurn={shownTurn}
            onOpenTurn={changeOpenTurn}
            recordView={recordView}
            onRecordViewChange={changeRecordView}
            toolbarExtra={<RecordViewToggle view={recordView} onChange={changeRecordView} />}
            renderTurnRecords={(call) => <TurnRawRecords result={result} call={call} lines={lines} view={recordView} />}
          />
          <FinalMessagePanel text={result.final_text} />
        </>
      ) : error ? null : (
        <Text render="p" color="$muted" fontFamily="$body" fontSize={14} data-xh-loading="result">
          loading result…
        </Text>
      )}
    </View>
  );
}
