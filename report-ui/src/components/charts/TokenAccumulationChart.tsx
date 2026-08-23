import { useMemo } from "react";
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { ChartPanel } from "@/components/charts/common";
import { axisProps, compact, GRID, numberFormatter } from "@/components/charts/chartStyle";
import { accumulation, sessionLabel } from "@/lib/series";
import type { Cell, RunResult } from "@/lib/types";

interface Props {
  cells: Cell[];
  /** the loaded result per session id; sessions without one (no ledger, or still loading) are skipped */
  results: Record<string, RunResult | null | undefined>;
}

/** One line per session with a ledger: `accumulative_billed_tokens` so far, turn by turn (glossary: `TokenAccumulationChart`). */
export function TokenAccumulationChart({ cells, results }: Props) {
  const { data, config, keys } = useMemo(() => {
    const withLedger = cells.filter((c) => c.has_ledger && results[c.session_id]?.calls?.length);
    const byTurn = new Map<number, Record<string, number>>();
    const config: ChartConfig = {};
    const keys: string[] = [];
    withLedger.forEach((c, i) => {
      const key = c.session_id;
      keys.push(key);
      // Fixed order, never cycled: a ninth session folds onto the last token colour rather than inventing one.
      config[key] = { label: sessionLabel(c), color: `var(--xh-series-${Math.min(i + 1, 8)})` };
      for (const p of accumulation(results[key]!.calls)) {
        const row = byTurn.get(p.n) ?? { n: p.n };
        row[key] = p.billed;
        byTurn.set(p.n, row);
      }
    });
    const data = [...byTurn.values()].sort((a, b) => a.n! - b.n!);
    return { data, config, keys };
  }, [cells, results]);

  return (
    <ChartPanel id="TokenAccumulationChart" title="accumulative_billed_tokens accumulating per turn">
      {keys.length ? (
        <ChartContainer config={config} className="aspect-auto h-[420px] w-full">
          <LineChart data={data} margin={{ top: 12, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis
              dataKey="n"
              type="number"
              domain={["dataMin", "dataMax"]}
              allowDecimals={false}
              label={{ value: "turn", position: "insideBottom", offset: -4, fill: "var(--xh-muted)", fontSize: 11 }}
              {...axisProps}
            />
            <YAxis
              tickFormatter={compact}
              width={56}
              label={{ value: "accumulative_billed_tokens so far", angle: -90, position: "insideLeft", fill: "var(--xh-muted)", fontSize: 11 }}
              {...axisProps}
            />
            <ChartTooltip
              content={
                <ChartTooltipContent
                  labelFormatter={(v) => `turn ${v}`}
                  formatter={(value, name) => [numberFormatter(value), config[String(name)]?.label ?? name]}
                />
              }
            />
            <ChartLegend content={<ChartLegendContent />} />
            {keys.map((key) => (
              <Line
                key={key}
                dataKey={key}
                type="monotone"
                stroke={`var(--color-${key})`}
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
                connectNulls
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ChartContainer>
      ) : (
        <p className="text-muted-foreground text-sm">No session with a per-call ledger yet; run the evals or the replay.</p>
      )}
    </ChartPanel>
  );
}
