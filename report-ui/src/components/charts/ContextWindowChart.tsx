import { useMemo } from "react";
import type { Data } from "plotly.js";
import { ChartPanel } from "@/components/charts/common";
import { Plot } from "@/components/charts/Plot";
import { axis, baseLayout, turnMarks, useChartTheme } from "@/components/charts/plotly";
import { fmt, pct, windowLabel } from "@/lib/format";
import { type AxisMode, stepSeries } from "@/lib/series";
import type { RunResult } from "@/lib/types";

interface Props {
  result: RunResult;
  lines: string[] | null;
  mode: AxisMode;
}

/** Context window consumption per turn, or as a step per session-log line (glossary: `ContextWindowChart`). */
export function ContextWindowChart({ result, lines, mode }: Props) {
  const theme = useChartTheme();
  const window = result.context_window;
  const perLine = mode === "line" && window;
  const step = useMemo(() => (perLine ? stepSeries<number | null>(result, lines, (k) => k.context_pct, null) : null), [perLine, result, lines]);

  const { traces, layout } = useMemo(() => {
    const yaxis = { ...axis(theme, { title: `% of ${windowLabel(window)} window` }), rangemode: "tozero" as const };
    if (step) {
      const traces: Data[] = [
        {
          type: "scatter",
          mode: "lines",
          name: "context % of window",
          x: step.x,
          y: step.y,
          line: { color: theme.accent, width: 2, shape: "hv" },
          connectgaps: false,
          hovertemplate: "%{y:.2f}% at L%{x}<extra></extra>",
        },
      ];
      const layout = baseLayout(theme, {
        hovermode: "closest",
        xaxis: { ...axis(theme, { title: "session-log line" }), range: [1, step.x.length], tickformat: ",d" },
        yaxis,
        ...turnMarks(theme, step.starts),
        margin: { t: 28, r: 16, b: 44, l: 64 },
      });
      return { traces, layout };
    }
    const points = [
      ...result.calls.map((k) => ({ label: `t${k.n}`, pct: k.context_pct, tokens: k.context_tokens })),
      { label: "final", pct: result.final_context_pct, tokens: result.final_context_tokens },
    ];
    const traces: Data[] = [
      {
        type: "scatter",
        mode: "lines+markers",
        name: "context % of window",
        x: points.map((p) => p.label),
        y: points.map((p) => p.pct),
        customdata: points.map((p) => fmt(p.tokens)),
        line: { color: theme.accent, width: 2 },
        marker: { size: 7 },
        hovertemplate: "%{y:.2f}% · %{customdata} tokens<extra></extra>",
      },
    ];
    const layout = baseLayout(theme, { hovermode: "closest", xaxis: axis(theme), yaxis });
    return { traces, layout };
  }, [theme, step, result, window]);

  if (!window) {
    return (
      <ChartPanel
        id="ContextWindowChart"
        title="Context window consumption"
        note={
          <span id="ContextWindowNote" className="warn">
            The harness reported no context window for this model, so consumption cannot be expressed as a percentage; the per-turn prompt sizes are in the turn
            table.
          </span>
        }
      >
        <div style={{ height: 320 }} />
      </ChartPanel>
    );
  }

  const peakFinal = (
    <>
      Peak <b>{pct(result.context_window_pct)}</b>, final <b>{pct(result.final_context_pct)}</b>.
    </>
  );
  const note = step ? (
    <span id="ContextWindowNote">
      Per session-log line: the prompt size the provider reported for the latest turn measured at or before that line, as a percentage of the{" "}
      <b>{fmt(window)}</b>
      -token window. Tool results between turn starts are already counted in the next turn's measurement. {peakFinal}
    </span>
  ) : (
    <span id="ContextWindowNote">
      Each point is the prompt that turn processed as reported by the provider (input + cache read + cache write), as a percentage of the <b>{fmt(window)}</b>
      -token window; the last point adds the final turn's output. These are measured figures: whatever the server kept or dropped of earlier thinking is already
      inside them. {peakFinal}
    </span>
  );

  return (
    <ChartPanel id="ContextWindowChart" title="Context window consumption" note={note}>
      <Plot data={traces} layout={layout} height={320} ariaLabel="Context window consumption" />
    </ChartPanel>
  );
}
