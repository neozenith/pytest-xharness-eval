/**
 * Mountable wrappers for the chart pieces whose props cannot cross from the test runner as-is:
 * a `ReadonlySet` (`hidden`) and a synchronous function (`valueOf`). Each takes a plain value
 * instead and builds the real prop inside the browser.
 */
import { ChartLegend, PlotWithLegend, type LegendItem } from "../src/components/charts/Plot";
import { PerTurnBars } from "../src/components/charts/perTurnBars";
import type { AxisMode } from "../src/lib/series";
import type { Data, Layout } from "plotly.js";
import type { Call, RunResult, Usage } from "../src/lib/types";

export const LegendWithHidden = ({
  items,
  hidden,
  onToggle,
  maxHeight,
}: {
  items: LegendItem[];
  hidden: string[];
  onToggle?: (key: string) => void;
  maxHeight?: number;
}) => <ChartLegend items={items} hidden={new Set(hidden)} onToggle={onToggle} maxHeight={maxHeight} />;

export const PlotWithLegendHidden = (props: {
  data: Data[];
  layout: Partial<Layout>;
  height: number;
  ariaLabel: string;
  items: LegendItem[];
  hidden: string[];
  onToggle?: (key: string) => void;
}) => <PlotWithLegend {...props} hidden={new Set(props.hidden)} />;

/** `PerTurnBars` reading each series' value straight off `call.usage[key]`. */
export const UsageBars = (props: {
  id: string;
  title: string;
  yLabel: string;
  series: { key: string; label: string; color: string }[];
  result: RunResult;
  lines: string[] | null;
  mode: AxisMode;
}) => <PerTurnBars {...props} valueOf={(k: Call, key: string) => k.usage[key as keyof Usage] ?? 0} />;
