import { Text, View } from "tamagui";
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
    <View render="section" id="SweepOverview" gap={16} data-el="SweepOverview">
      <Card>
        <CardContent>
          <TokenAccumulationChart cells={index.cells} results={results} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>
            Sessions{" "}
            <Text render={<span id="SessionCount" />} color="$muted" fontWeight="400">
              ({index.cells.length})
            </Text>
            <El name="SessionTable" />
          </CardTitle>
          <CardDescription>One row per captured session. Click a row to open its SessionView; a header to sort; an id to copy it.</CardDescription>
        </CardHeader>
        <CardContent>
          <SessionTable cells={index.cells} />
        </CardContent>
      </Card>
    </View>
  );
}
