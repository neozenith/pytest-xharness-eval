import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { El } from "@/components/El";
import { short, usd, when } from "@/lib/format";
import type { Mode } from "@/lib/tokens";
import type { Cell, Index } from "@/lib/types";

interface Props {
  index: Index | null;
  cell: Cell | undefined;
  mode: Mode;
  onToggleMode: () => void;
}

/**
 * The page header. On the sweep the title is the report's; inside a SessionView it is the
 * eval · session · harness · model tuple, so the tab and the top line say where you are.
 */
export function ReportHeader({ index, cell, mode, onToggleMode }: Props) {
  const total = index ? index.cells.reduce((s, c) => s + (c.estimated_cost_usd ?? 0), 0) : 0;
  return (
    <header id="ReportHeader" className="bg-card sticky top-0 z-10 flex flex-wrap items-baseline gap-x-4 gap-y-2 border-b px-6 py-3">
      <h1 id="ReportTitle" className="flex items-baseline gap-2 text-lg font-semibold tracking-tight">
        <a href="#" className="hover:underline">
          {cell ? "xharness" : "xharness eval report"}
        </a>
        {cell ? (
          <>
            <span className="text-muted-foreground font-normal">›</span>
            <span>{cell.case}</span>
            <span className="text-muted-foreground font-normal">·</span>
            <code className="font-mono text-base">{short(cell.session_id)}</code>
            <span className="text-muted-foreground font-normal">·</span>
            <span>{cell.harness}</span>
            <span className="text-muted-foreground font-normal">·</span>
            <code className="font-mono text-base">{cell.model}</code>
          </>
        ) : null}
        <El name="ReportTitle" />
      </h1>
      <span id="ReportMeta" className="text-muted-foreground text-sm">
        {index ? (
          <>
            {index.cells.length} session(s) · estimated {usd(total)} · generated {when(index.generated_at)}
            {index.inline ? " · inline" : ""}
          </>
        ) : (
          "loading…"
        )}
      </span>
      <span className="flex-1" />
      <Button id="ThemeToggle" variant="outline" size="icon-sm" onClick={onToggleMode} title="toggle light / dark" aria-label="toggle light / dark">
        {mode === "dark" ? <Sun /> : <Moon />}
      </Button>
    </header>
  );
}
