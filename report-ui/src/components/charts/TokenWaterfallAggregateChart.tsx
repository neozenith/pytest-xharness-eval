import { useMemo } from "react";
import type { Data } from "plotly.js";
import { ChartPanel } from "@/components/charts/common";
import { PlotWithLegend, useHiddenSeries, type LegendItem } from "@/components/charts/Plot";
import { CATEGORIES, TOTAL } from "@/components/charts/TokenWaterfallChart";
import { axis, baseLayout, useChartTheme } from "@/components/charts/plotly";
import { aggregateWaterfall } from "@/lib/series";
import type { Cell, RunResult } from "@/lib/types";

interface Props {
  cells: Cell[];
  /** the loaded result per session id; sessions without one (no ledger, or still loading) are skipped */
  results: Record<string, RunResult | null | undefined>;
}

const SPREAD_KEY = "spread";
const SPREAD_LABEL = "min–max across runs";

const NOTE =
  "Where the tokens went, averaged over every run in view: each column is the mean over the runs that reached that turn, faded in proportion to how many, with their min–max spread as a whisker.";

/**
 * How solid a column is drawn: the share of the runs that reached it. A turn only one run of
 * twenty-four survived to is a mean of one, and drawing it at the same strength as turn 1 — a
 * mean of twenty-four — would let the eye read a thinning tail as a rising trend. The floor keeps
 * a one-run column visible rather than erasing it; the whisker on it collapses to a point, which
 * is the other half of the same signal.
 */
const solidity = (n: number, runs: number): number => (runs ? 0.25 + 0.75 * (n / runs) : 1);

/**
 * The aggregate of `TokenWaterfallChart` over the filtered sweep: a mean waterfall from
 * `baseline_tokens` to `accumulative_billed_tokens`, with a min–max whisker per column
 * (glossary: `TokenWaterfallAggregateChart`).
 */
export function TokenWaterfallAggregateChart({ cells, results }: Props) {
  const theme = useChartTheme();
  const { hidden, toggle } = useHiddenSeries();
  const agg = useMemo(() => aggregateWaterfall(cells, results), [cells, results]);

  const { traces, legend } = useMemo(() => {
    const legend: LegendItem[] = [
      ...[...CATEGORIES, TOTAL].map((c) => ({ key: c.key, label: c.label, color: theme.waterfall[c.key] ?? theme.accent })),
      { key: SPREAD_KEY, label: SPREAD_LABEL, color: theme.muted },
    ];
    const labels = agg.columns.map((c) => c.label);
    const opacity = agg.n.map((count) => solidity(count, agg.runs));
    const means = agg.columns.map((c, i) => (agg.n[i] ? c.base + c.baseline + c.read + c.context + c.thinking + c.output + c.sub + c.total : 0));
    const traces: Data[] = [
      // the invisible riser every stacked segment sits on, exactly as the per-session chart draws it
      { type: "bar", name: "base", x: labels, y: agg.columns.map((c) => c.base), marker: { color: "rgba(0,0,0,0)" }, hoverinfo: "skip" },
      ...[...CATEGORIES, TOTAL].map((c): Data => ({
        type: "bar",
        name: c.label,
        x: labels,
        // a zero segment renders nothing and must not clutter the unified hover
        y: agg.columns.map((col) => col[c.key] || null),
        marker: { color: theme.waterfall[c.key], opacity, line: { color: theme.plot, width: 1 } },
        visible: hidden.has(c.key) ? "legendonly" : true,
        customdata: agg.n.map((count): number[] => [count]),
        hovertemplate: `%{y:,.0f} mean of %{customdata[0]} run(s) · ${c.label}<extra></extra>`,
      })),
      /*
       * The whisker rides the top of each stack rather than a second axis: it is the same
       * quantity the bars sum to, so a reader compares a run's spread against the mean it
       * brackets without converting between two scales. Asymmetric by construction — min and max
       * are the real extremes, not a symmetric deviation the data never had.
       */
      {
        type: "scatter",
        mode: "markers",
        name: SPREAD_LABEL,
        x: labels,
        y: means,
        marker: { size: 1, color: theme.muted },
        error_y: {
          type: "data",
          symmetric: false,
          array: agg.max.map((v, i) => Math.max(v - means[i]!, 0)),
          arrayminus: agg.min.map((v, i) => Math.max(means[i]! - v, 0)),
          color: theme.muted,
          thickness: 1.5,
          width: 5,
        },
        visible: hidden.has(SPREAD_KEY) ? "legendonly" : true,
        customdata: agg.n.map((count, i): number[] => [agg.min[i]!, agg.max[i]!, count]),
        hovertemplate: "%{y:,.0f} mean · %{customdata[0]:,}–%{customdata[1]:,} across %{customdata[2]} run(s)<extra></extra>",
      },
    ];
    return { traces, legend };
  }, [agg, theme, hidden]);

  const layout = useMemo(
    () =>
      baseLayout(theme, {
        barmode: "stack",
        bargap: 0.25,
        hovermode: "x unified",
        xaxis: axis(theme),
        yaxis: axis(theme, { title: "mean tokens", compact: true }),
      }),
    [theme],
  );

  return (
    <ChartPanel id="TokenWaterfallAggregateChart" title={`Token waterfall, averaged over ${agg.runs} run${agg.runs === 1 ? "" : "s"}`} note={NOTE}>
      {agg.runs ? (
        <PlotWithLegend
          data={traces}
          layout={layout}
          height={420}
          ariaLabel="Mean token waterfall from baseline to accumulative billed tokens across the runs in view, with the min to max spread per column"
          items={legend}
          hidden={hidden}
          onToggle={toggle}
        />
      ) : (
        <p className="muted" style={{ fontSize: "0.875rem" }}>
          No session with a per-call ledger in view; clear the filters, or run the evals or the replay.
        </p>
      )}
    </ChartPanel>
  );
}
