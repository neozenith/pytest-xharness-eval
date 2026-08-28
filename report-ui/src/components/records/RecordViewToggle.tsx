import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { El } from "@/components/El";
import type { RecordView } from "./RecordCard";

/** How every record card renders: the rendered view or the raw JSON (glossary: `RecordViewToggle`). */
export function RecordViewToggle({ view, onChange }: { view: RecordView; onChange: (v: RecordView) => void }) {
  return (
    <span id="RecordViewToggle" style={{ display: "inline-flex", alignItems: "center" }} title="how each log record renders" data-el="RecordViewToggle">
      <ToggleGroup type="single" variant="outline" size="sm" value={view} onValueChange={(v) => v && onChange(v as RecordView)}>
        <ToggleGroupItem value="nice" data-rv="nice">
          nice records
        </ToggleGroupItem>
        <ToggleGroupItem value="raw" data-rv="raw">
          raw JSON
        </ToggleGroupItem>
      </ToggleGroup>
      <El name="RecordViewToggle" />
    </span>
  );
}
