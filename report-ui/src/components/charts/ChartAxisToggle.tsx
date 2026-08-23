import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { El } from "@/components/El";
import type { AxisMode } from "@/lib/series";

interface Props {
  mode: AxisMode;
  onChange: (mode: AxisMode) => void;
}

/** The x-axis of the four per-turn charts: per turn, or per session-log line (glossary: `ChartAxisToggle`). */
export function ChartAxisToggle({ mode, onChange }: Props) {
  return (
    <div id="ChartAxisToggle" data-el="ChartAxisToggle" className="flex flex-wrap items-center gap-3 text-sm" title="x-axis of the four per-turn charts">
      <span className="text-muted-foreground">Chart x-axis:</span>
      <ToggleGroup type="single" variant="outline" size="sm" value={mode} onValueChange={(v) => v && onChange(v as AxisMode)} aria-label="chart x-axis">
        <ToggleGroupItem value="turn">per turn</ToggleGroupItem>
        <ToggleGroupItem value="line">per session-log line</ToggleGroupItem>
      </ToggleGroup>
      <span className="text-muted-foreground">
        — per line, a value holds from the record that measured it until the next measurement; turn starts are marked.
      </span>
      <El name="ChartAxisToggle" />
    </div>
  );
}
