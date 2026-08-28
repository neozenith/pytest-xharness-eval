import { useMemo } from "react";
import type { Data, Layout } from "plotly.js";
import { ChartPanel } from "@/components/charts/common";
import { PlotWithLegend, useHiddenSeries, type LegendItem } from "@/components/charts/Plot";
import { axis, baseLayout, turnMarks, useChartTheme, type ChartTheme } from "@/components/charts/plotly";
import { cumulativeCostByTurn, stepSeries, waterfallByLine, waterfallColumns, type AxisMode } from "@/lib/series";
import type { RunResult } from "@/lib/types";

interface Props {
  result: RunResult;
  lines: string[] | null;
  mode: AxisMode;
}

/** The five visible categories of the waterfall, in stacking order, coloured by the `waterfall` design tokens. */
const CATEGORIES: { key: "baseline" | "read" | "context" | "thinking" | "output" | "sub"; label: string }[] = [
  { key: "baseline", label: "baseline_tokens (harness)" },
  { key: "read", label: "cache read (re-read context)" },
  { key: "context", label: "new context (input + cache write)" },
  { key: "thinking", label: "thinking" },
  { key: "output", label: "visible output" },
  { key: "sub", label: "subagents (spawned threads' bill)" },
];
const TOTAL = { key: "total" as const, label: "accumulative_billed_tokens" };
const COST_KEY = "cost";
const COST_LABEL = "accumulative cost (est. USD)";

const NOTE =
  "Starts at baseline_tokens (the harness's own prompt on turn 1); each turn adds the cache it re-read, the new context it ingested, its thinking, its visible output, and the whole bill of any subagent it spawned. The last bar is accumulative_billed_tokens. The line on the right axis is the running estimated cost, priced with rates_applied.";

const legendItems = (theme: ChartTheme, withTotal: boolean, withCost: boolean): LegendItem[] => [
  ...[...CATEGORIES, ...(withTotal ? [TOTAL] : [])].map((c) => ({ key: c.key, label: c.label, color: theme.waterfall[c.key] ?? theme.accent })),
  ...(withCost ? [{ key: COST_KEY, label: COST_LABEL, color: theme.accent }] : []),
];

/** The right-hand USD axis the cost line rides on: overlays the token axis, draws no second grid. */
const costAxis = (theme: ChartTheme): Partial<Layout["yaxis"]> => ({
  ...axis(theme, { title: "estimated USD so far" }),
  overlaying: "y",
  side: "right",
  tickprefix: "$",
  showgrid: false,
  zeroline: false,
  rangemode: "tozero",
});

const costTrace = (theme: ChartTheme, x: (string | number)[], y: (number | null)[], hidden: ReadonlySet<string>, shape?: "hv"): Data => ({
  type: "scatter",
  mode: shape ? "lines" : "lines+markers",
  name: COST_LABEL,
  x,
  y,
  yaxis: "y2",
  line: { color: theme.accent, width: 2, ...(shape ? { shape } : {}) },
  marker: { size: 5 },
  visible: hidden.has(COST_KEY) ? "legendonly" : true,
  hovertemplate: `$%{y:.4f} · ${COST_LABEL}<extra></extra>`,
});

/**
 * Per turn: a waterfall of stacked bars from `baseline_tokens` to `accumulative_billed_tokens`,
 * with the running estimated USD overlaid as a line on a second y axis; per session-log line:
 * the same categories as a stacked step area of cumulative tokens, turn starts marked
 * (glossary: `TokenWaterfallChart`).
 */
export function TokenWaterfallChart({ result, lines, mode }: Props) {
  const theme = useChartTheme();
  const { hidden, toggle } = useHiddenSeries();
  const columns = useMemo(() => waterfallColumns(result), [result]);
  const byLine = useMemo(() => (mode === "line" ? waterfallByLine(result, lines) : null), [mode, result, lines]);
  const cost = useMemo(() => cumulativeCostByTurn(result), [result]);

  const { traces, layout, legend } = useMemo(() => {
    if (byLine) {
      const legend = legendItems(theme, false, cost != null);
      const traces: Data[] = CATEGORIES.map((c) => ({
        type: "scatter",
        mode: "lines",
        name: c.label,
        stackgroup: "tokens",
        x: byLine.rows.map((r) => r.line),
        // the cumulative rows carry the baseline as `base`
        y: byLine.rows.map((r) => (c.key === "baseline" ? r.base : r[c.key])),
        line: { color: theme.plot, width: 1, shape: "hv" },
        fillcolor: theme.waterfall[c.key],
        visible: hidden.has(c.key) ? "legendonly" : true,
        hovertemplate: `%{y:,} · ${c.label}<extra></extra>`,
      }));
      if (cost != null) {
        // the cost the latest measured turn has accumulated, held as a step per log line
        const step = stepSeries<number | null>(result, lines, (_k, t) => cost[t] ?? null, null);
        traces.push(costTrace(theme, step.x, step.y, hidden, "hv"));
      }
      const layout = baseLayout(theme, {
        xaxis: { ...axis(theme, { title: "session-log line" }), range: [1, byLine.rows.length], tickformat: ",d" },
        yaxis: axis(theme, { title: "accumulative_billed_tokens so far", compact: true }),
        ...(cost != null ? { yaxis2: costAxis(theme) } : {}),
        ...turnMarks(theme, byLine.starts),
        margin: { t: 28, r: 16, b: 44, l: 64 },
      });
      return { traces, layout, legend };
    }

    const legend = legendItems(theme, true, cost != null);
    const riser: Data = {
      type: "bar",
      name: "base",
      x: columns.map((c) => c.label),
      y: columns.map((c) => c.base),
      marker: { color: "rgba(0,0,0,0)" },
      hoverinfo: "skip",
    };
    const traces: Data[] = [
      riser,
      ...[...CATEGORIES, TOTAL].map((c): Data => ({
        type: "bar",
        name: c.label,
        x: columns.map((col) => col.label),
        // a zero segment renders nothing and must not clutter the unified hover
        y: columns.map((col) => col[c.key] || null),
        marker: { color: theme.waterfall[c.key], line: { color: theme.plot, width: 1 } },
        visible: hidden.has(c.key) ? "legendonly" : true,
        hovertemplate: `%{y:,} · ${c.label}<extra></extra>`,
      })),
    ];
    if (cost != null) {
      // rides the same category axis: zero at the baseline column, the estimate's total at the last
      traces.push(costTrace(theme, ["baseline", ...result.calls.map((k) => `t${k.n}`), "total"], [0, ...cost, result.estimated_cost_usd], hidden));
    }
    const layout = baseLayout(theme, {
      barmode: "stack",
      bargap: 0.25,
      xaxis: axis(theme),
      yaxis: axis(theme, { title: "tokens", compact: true }),
      ...(cost != null ? { yaxis2: costAxis(theme) } : {}),
    });
    return { traces, layout, legend };
  }, [theme, hidden, byLine, columns, cost, result, lines]);

  return (
    <ChartPanel id="TokenWaterfallChart" title="Token waterfall" note={NOTE}>
      <PlotWithLegend
        data={traces}
        layout={layout}
        height={440}
        ariaLabel="Token waterfall from baseline to accumulative billed tokens, with the running estimated cost on a second axis"
        items={legend}
        hidden={hidden}
        onToggle={toggle}
      />
    </ChartPanel>
  );
}
