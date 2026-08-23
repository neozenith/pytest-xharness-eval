import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { El } from "@/components/El";
import { fmt } from "@/lib/format";
import { Chip, Notice, Pill } from "./shared";

/** Every record kind seen in the session log with its count, the pill coloured by category. */
export function RecordKindsPanel({ recordKinds }: { recordKinds: Record<string, number> | null | undefined }) {
  const entries = Object.entries(recordKinds ?? {});
  return (
    <Card data-el="RecordKindsPanel">
      <CardHeader>
        <CardTitle>
          Record kinds in this session
          <El name="RecordKindsPanel" />
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div id="RecordKindsPanel" className="flex flex-wrap gap-2">
          {entries.length ? (
            entries.map(([k, n]) => (
              <Chip key={k}>
                <Pill kind={k} /> {fmt(n)}
              </Chip>
            ))
          ) : (
            <Notice>no record_kinds on this result (predates ADR 0022)</Notice>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
