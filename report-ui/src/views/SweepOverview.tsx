import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { TokenAccumulationChart } from "@/components/charts";
import { El } from "@/components/El";
import { SessionTable } from "@/components/SessionTable";
import { useResults } from "@/hooks/useResults";
import type { Index } from "@/lib/types";

/** Every captured session at a glance (glossary: `SweepOverview`). */
export function SweepOverview({ index }: { index: Index }) {
  const results = useResults(index.cells);
  return (
    <section id="SweepOverview" className="space-y-4" data-el="SweepOverview">
      <Card>
        <CardContent>
          <TokenAccumulationChart cells={index.cells} results={results} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>
            Sessions{" "}
            <span id="SessionCount" className="text-muted-foreground font-normal">
              ({index.cells.length})
            </span>
            <El name="SessionTable" />
          </CardTitle>
          <CardDescription>One row per captured session. Click a row to open its SessionView; a header to sort; an id to copy it.</CardDescription>
        </CardHeader>
        <CardContent>
          <SessionTable cells={index.cells} />
        </CardContent>
      </Card>
    </section>
  );
}
