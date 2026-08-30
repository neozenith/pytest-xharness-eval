import { useMemo } from "react";
import type { Data } from "plotly.js";
import { ChartPanel } from "@/components/charts/common";
import { PlotWithLegend, useHiddenSeries } from "@/components/charts/Plot";
import { axis, baseLayout, seriesColor, seriesDash, useChartTheme } from "@/components/charts/plotly";
import { NO_MATCH } from "@/lib/facets";
import { accumulationGroups } from "@/lib/series";
import type { Cell, RunResult } from "@/lib/types";

interface Props {
  cells: Cell[];
  /** the loaded result per session id; sessions without one (no ledger, or still loading) are skipped */
  results: Record<string, RunResult | null | undefined>;
}

/** `#rrggbb` at low opacity for the min–max envelope; non-hex tokens fall back to a neutral wash. */
const envelope = (color: string): string => (/^#[0-9a-fA-F]{6}$/.test(color) ? `${color}26` : "rgba(128,128,128,0.15)");

/**
 * `accumulative_billed_tokens` accumulating per turn, aggregated across runs: one mean line
 * per suite × harness × model, with a min–max envelope when the group holds more than one
 * run (glossary: `TokenAccumulationChart`).
 */
export function TokenAccumulationChart({ cells, results }: Props) {
  const theme = useChartTheme();
  const { hidden, toggle } = useHiddenSeries();

  const { traces, legend } = useMemo(() => {
    const groups = accumulationGroups(cells, results);
    const legend = groups.map((g, i) => ({ key: g.key, label: g.label, color: seriesColor(theme, i) }));
    const traces: Data[] = groups.flatMap((g, i): Data[] => {
      const color = seriesColor(theme, i);
      const visible = hidden.has(g.key) ? ("legendonly" as const) : true;
      const band: Data[] =
        g.runs > 1
          ? [
              { type: "scatter", mode: "lines", x: g.turns, y: g.max, line: { width: 0 }, hoverinfo: "skip", visible, showlegend: false },
              {
                type: "scatter",
                mode: "lines",
                x: g.turns,
                y: g.min,
                line: { width: 0 },
                fill: "tonexty",
                fillcolor: envelope(color),
                hoverinfo: "skip",
                visible,
                showlegend: false,
              },
            ]
          : [];
      return [
        ...band,
        {
          type: "scatter",
          mode: "lines+markers",
          name: g.label,
          x: g.turns,
          y: g.mean,
          line: { color, width: 2, dash: seriesDash(theme, i) },
          marker: { size: 5 },
          visible,
          hovertemplate: `%{y:,} ${g.runs > 1 ? "mean " : ""}after turn %{x} · ${g.label}<extra></extra>`,
        },
      ];
    });
    return { traces, legend };
  }, [cells, results, theme, hidden]);

  const layout = useMemo(
    () =>
      baseLayout(theme, {
        hovermode: "closest",
        xaxis: { ...axis(theme, { title: "turn" }), rangemode: "tozero", tickformat: ",d" },
        yaxis: axis(theme, { title: "accumulative_billed_tokens so far", compact: true }),
      }),
    [theme],
  );

  return (
    <ChartPanel
      id="TokenAccumulationChart"
      title="accumulative_billed_tokens accumulating per turn"
      note="One line per suite × harness × model, averaged across its runs; the shaded envelope is the min–max spread when a cell ran more than once."
    >
      {legend.length ? (
        <PlotWithLegend
          data={traces}
          layout={layout}
          height={420}
          ariaLabel="Billed tokens accumulating per turn, one aggregated line per suite, harness and model"
          items={legend}
          hidden={hidden}
          onToggle={toggle}
        />
      ) : (
        /*
         * Two different nothings. Handed no cells at all the chart has been filtered to nothing
         * and says so; only when there are cells but none of them carries a ledger is the
         * no-ledger sentence true. A filtered-to-nothing chart must not accuse the reader of
         * having no ledger.
         */
        <p className="muted" style={{ fontSize: "0.875rem" }}>
          {cells.length === 0 ? NO_MATCH : "No session with a per-call ledger yet; run the evals or the replay."}
        </p>
      )}
    </ChartPanel>
  );
}
