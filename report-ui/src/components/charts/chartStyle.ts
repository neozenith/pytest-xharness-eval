/** Axis styling and number formatting every chart shares; the grid and surface come from the design tokens. */
import type { XAxisProps, YAxisProps } from "recharts";
import { fmt } from "@/lib/format";

/** Ticks and grid stay recessive: muted ink, no axis line. */
export const axisProps = { tick: { fill: "var(--xh-muted)", fontSize: 11 }, axisLine: false, tickLine: false } satisfies Partial<XAxisProps & YAxisProps>;

export const GRID = "var(--xh-grid)";
export const SURFACE = "var(--xh-plot)";

export const compact = (n: number): string => (Math.abs(n) >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : Math.abs(n) >= 1e3 ? `${Math.round(n / 1e3)}k` : String(n));

export const numberFormatter = (value: unknown): string => (typeof value === "number" ? fmt(value) : String(value ?? ""));
