import { useMemo } from "react";
import { Text, View } from "tamagui";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { TokenAccumulationChart, TokenWaterfallAggregateChart } from "@/components/charts";
import { El } from "@/components/El";
import { OverviewFilters } from "@/components/OverviewFilters";
import { SessionSummaryTable } from "@/components/SessionSummaryTable";
import { SessionTable } from "@/components/SessionTable";
import { useResults } from "@/hooks/useResults";
import { FACETS, filterCells } from "@/lib/facets";
import { modelShortNames } from "@/lib/format";
import { summaryRows } from "@/lib/summary";
import { NO_FACETS, useRoute } from "@/lib/route";
import type { Index } from "@/lib/types";

/**
 * Every captured session at a glance (glossary: `SweepOverview`).
 *
 * The view owns the filtering (ADR 0042): it derives the visible cells ONCE and hands the same
 * array to all three consumers, which stay presentational and know nothing about facets.
 */
export function SweepOverview({ index }: { index: Index }) {
  const route = useRoute();
  const facets = route.view === "overview" ? route.facets : NO_FACETS;
  /*
   * The UNFILTERED list on purpose. Keying this on the filtered array would re-run the effect on
   * every chip click, re-fetch every result and re-raise `window.__XH_PENDING__` — which is the
   * settledness contract the whole e2e matrix waits on (ADR 0031), not merely a flash of chart.
   */
  const results = useResults(index.cells);
  const cells = useMemo(() => filterCells(index.cells, facets), [index.cells, facets]);
  const filtered = FACETS.some((facet) => facets[facet] != null);
  /*
   * The two tables state their size in the same words, in the same place, in the same voice —
   * `16` groups over `24` sessions — because that pairing is the whole point of stacking them:
   * one is the other rolled up, and the reader should be able to see the ratio without counting
   * rows. `SessionSummaryTable` groups again internally; this is a group-by over two dozen
   * rows, not a reason to thread a second array through the view.
   */
  const groups = useMemo(() => summaryRows(cells).length, [cells]);
  /*
   * Derived from the UNFILTERED sweep, so a model's printed name is a property of the report and
   * not of the reader's current selection: filtering to one harness must not silently re-expand
   * (or further shorten) the names in the two tables under it.
   */
  const shortModel = useMemo(() => modelShortNames(index.cells.map((c) => c.model)), [index.cells]);

  return (
    <View render="section" id="SweepOverview" gap={16} data-el="SweepOverview">
      <OverviewFilters cells={index.cells} />
      {/*
       * The two charts read as one row because they are one question asked two ways over the same
       * filtered population: how fast the bill grows, and where it went. Side by side a reader
       * compares a spike in the accumulation against the category that caused it without holding
       * one in their head while scrolling to the other.
       *
       * `auto-fit` rather than a fixed pair: below a ~960px container two 460px columns do not
       * exist, and the charts stack rather than being squeezed to a width their axes cannot
       * carry. Each chart's own `PlotWithLegend` then wraps its legend beneath the plot, so a
       * narrow column spends its width on the plot rather than on a 240px legend rail.
       */}
      <View
        id="OverviewCharts"
        data-el="OverviewCharts"
        style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(460px, 1fr))", gap: 16, alignItems: "stretch" }}
      >
        <Card>
          <CardContent>
            <TokenAccumulationChart cells={cells} results={results} />
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <TokenWaterfallAggregateChart cells={cells} results={results} />
          </CardContent>
        </Card>
      </View>
      <Card>
        <CardHeader>
          <CardTitle>
            Summary{" "}
            <Text render={<span id="SummaryCount" />} color="$muted" fontWeight="400">
              ({groups} {groups === 1 ? "group" : "groups"})
            </Text>
            <El name="SessionSummaryTable" />
          </CardTitle>
          <CardDescription>
            The same runs the table below lists, aggregated one row per line of the chart above: skill × case × harness × model, with a run count and the mean
            of each measure over the runs that carry it.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SessionSummaryTable cells={cells} shortModel={shortModel} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>
            Sessions{" "}
            <Text render={<span id="SessionCount" />} color="$muted" fontWeight="400">
              ({filtered ? `${cells.length} of ${index.cells.length}` : cells.length})
            </Text>
            <El name="SessionTable" />
          </CardTitle>
          <CardDescription>One row per captured session. Click a row to open its SessionView; a header to sort; an id to copy it.</CardDescription>
        </CardHeader>
        <CardContent>
          <SessionTable cells={cells} shortModel={shortModel} />
        </CardContent>
      </Card>
    </View>
  );
}
