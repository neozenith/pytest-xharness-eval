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

/** How strongly the min–max envelope is washed in its line's colour. */
const ENVELOPE_ALPHA = 0.15;

const RGB = /^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/i;

/**
 * The line's colour at `ENVELOPE_ALPHA`, for any colour a project's tokens may use (`#36c`,
 * `#4f46e5`, `rgb()`, a name, `hsl()`): hex is expanded here, and anything else is resolved by the
 * browser's own colour parser to `rgb()`. Plotly has no fill opacity for a scatter, and a trace's
 * `opacity` does not reach a `tonexty` fill (it is painted in the previous trace's group), so the
 * alpha has to be in the colour itself. Only a colour the browser cannot express as `rgb()` gets
 * the neutral wash, and Plotly could not have drawn its line either.
 */
const envelope = (color: string): string => {
  const hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(color)?.[1];
  const full = hex?.length === 3 ? [...hex].map((c) => c + c).join("") : hex;
  if (full)
    return `rgba(${Number.parseInt(full.slice(0, 2), 16)},${Number.parseInt(full.slice(2, 4), 16)},${Number.parseInt(full.slice(4, 6), 16)},${ENVELOPE_ALPHA})`;
  let m = RGB.exec(color);
  if (!m && typeof document !== "undefined") {
    const probe = document.createElement("span");
    probe.style.color = color;
    document.body.appendChild(probe);
    m = RGB.exec(getComputedStyle(probe).color);
    probe.remove();
  }
  return m ? `rgba(${m[1]},${m[2]},${m[3]},${ENVELOPE_ALPHA})` : `rgba(128,128,128,${ENVELOPE_ALPHA})`;
};

/**
 * `accumulative_billed_tokens` accumulating per turn, aggregated across runs: one mean line
 * per suite × harness × model × effort rung, with a min–max envelope when the group holds more than one
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
      note="One line per suite × harness × model × effort rung, averaged across its runs; the shaded envelope is the min–max spread when a cell ran more than once."
    >
      {legend.length ? (
        <PlotWithLegend
          data={traces}
          layout={layout}
          height={420}
          ariaLabel="Billed tokens accumulating per turn, one aggregated line per suite, harness, model and effort rung"
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
