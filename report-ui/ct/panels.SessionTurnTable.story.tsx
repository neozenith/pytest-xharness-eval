/**
 * A test story for `SessionTurnTable` (Playwright CT's documented pattern for props a spec
 * cannot pass across the Node/browser boundary). A function prop in CT is proxied back to the
 * Node runner and returns a Promise there, so a `renderTurnRecords` returning JSX mounts as an
 * async component and React refuses it ("An unknown Component is an async Client Component").
 * The story wires the records renderer in the browser, the way `SessionView` does, and owns
 * `view` / `openTurn` state so a spec can click through open → close → detailed with real
 * re-renders. Each change is also reported to the optional spy props, which are plain callbacks
 * and so cross to Node fine.
 */
import { useState } from "react";
import { SessionTurnTable } from "../src/components/panels/SessionTurnTable";
import { turnId } from "../src/components/panels/helpers";
import type { RecordView, TurnView } from "../src/lib/route";
import type { RunResult } from "../src/lib/types";

export interface TurnTableStoryProps {
  result: RunResult;
  view?: TurnView;
  openTurn?: number | null;
  /** When false the table gets no `renderTurnRecords`, so its own placeholder shows. */
  records?: boolean;
  /** When true the table's state is fixed: callbacks report but nothing re-renders. */
  controlledOnly?: boolean;
  onOpenTurnSpy?: (n: number | null) => void;
  onViewChangeSpy?: (v: TurnView) => void;
}

export function TurnTableStory({
  result,
  view: view0 = "summary",
  openTurn: open0 = null,
  records = true,
  controlledOnly = false,
  onOpenTurnSpy,
  onViewChangeSpy,
}: TurnTableStoryProps) {
  const [view, setView] = useState<TurnView>(view0);
  const [openTurn, setOpenTurn] = useState<number | null>(open0);
  const [recordView, setRecordView] = useState<RecordView>("nice");
  return (
    <SessionTurnTable
      result={result}
      view={view}
      onViewChange={(v) => {
        onViewChangeSpy?.(v);
        if (!controlledOnly) setView(v);
      }}
      openTurn={openTurn}
      onOpenTurn={(n) => {
        onOpenTurnSpy?.(n);
        if (!controlledOnly) setOpenTurn(n);
      }}
      recordView={recordView}
      onRecordViewChange={setRecordView}
      renderTurnRecords={
        records
          ? (k) => (
              <div id={turnId(result.session_id, k.n)} data-testid="turn-records" data-n={k.n}>
                records of t{k.n}: {k.records.join(",")}
              </div>
            )
          : undefined
      }
    />
  );
}
