import { XStack } from "tamagui";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { CardDescription } from "@/components/ui/card";
import { ControlLabel } from "@/components/charts/common";
import { El } from "@/components/El";
import type { AxisMode } from "@/lib/series";

interface Props {
  mode: AxisMode;
  onChange: (mode: AxisMode) => void;
}

/** The x-axis of the four per-turn charts: per turn, or per session-log line (glossary: `ChartAxisToggle`). */
export function ChartAxisToggle({ mode, onChange }: Props) {
  return (
    <XStack
      render={<div title="x-axis of the four per-turn charts" />}
      id="ChartAxisToggle"
      data-el="ChartAxisToggle"
      flexWrap="wrap"
      // Three text objects in a row: the label, the control's own labels and the gloss all sit
      // on one baseline. Centring them instead would rank them by box height, which is an
      // accident of the control, and drop the label ~8px below the gloss's first line.
      alignItems="baseline"
      columnGap={12}
      rowGap={8}
    >
      {/* The control is what the eye should land on, so the label leads it at panel-heading weight … */}
      <ControlLabel>
        Chart x-axis
        <El name="ChartAxisToggle" />
      </ControlLabel>
      <ToggleGroup type="single" variant="outline" size="sm" value={mode} onValueChange={(v) => v && onChange(v as AxisMode)} aria-label="chart x-axis">
        <ToggleGroupItem value="turn">per turn</ToggleGroupItem>
        <ToggleGroupItem value="line">per session-log line</ToggleGroupItem>
      </ToggleGroup>
      {/* … and the gloss is the same object as every other panel description, measure included. */}
      <CardDescription flexShrink={1}>
        Per line, a value holds from the record that measured it until the next measurement; turn starts are marked.
      </CardDescription>
    </XStack>
  );
}
