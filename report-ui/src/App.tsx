import { useEffect, useMemo, useState } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ReportHeader } from "@/components/ReportHeader";
import { loadIndex, loadTokens } from "@/lib/data";
import { useRoute } from "@/lib/route";
import { applyTokens, initialMode, rememberMode, type Mode } from "@/lib/tokens";
import type { DesignTokens, Index } from "@/lib/types";
import { SessionView } from "@/views/SessionView";
import { SweepOverview } from "@/views/SweepOverview";

export function App() {
  const [index, setIndex] = useState<Index | null>(null);
  const [tokens, setTokens] = useState<DesignTokens | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>(initialMode);
  const route = useRoute();

  useEffect(() => {
    loadIndex()
      .then(setIndex)
      .catch((e: unknown) => setError(`index.json: ${String(e)}`));
    loadTokens()
      .then(setTokens)
      .catch((e: unknown) => console.error("design tokens unavailable, using the fallback palette", e));
  }, []);

  useEffect(() => {
    if (tokens) applyTokens(tokens, mode);
    else document.documentElement.classList.toggle("dark", mode === "dark");
  }, [tokens, mode]);

  const toggleMode = () => {
    const next = mode === "dark" ? "light" : "dark";
    setMode(next);
    rememberMode(next);
  };

  const cell = useMemo(() => (route.view === "session" && index ? index.cells.find((c) => c.session_id === route.sessionId) : undefined), [route, index]);

  return (
    <TooltipProvider delayDuration={200}>
      <ReportHeader index={index} cell={cell} mode={mode} onToggleMode={toggleMode} />
      <main className="mx-auto max-w-[1600px] space-y-4 p-6">
        {error ? (
          <p className="text-destructive">
            {error}. The page fetches its data from beside itself: serve the captured directory over HTTP, or write it with{" "}
            <code>--xharness-report-inline</code>.
          </p>
        ) : !index ? (
          <p className="text-muted-foreground">loading…</p>
        ) : route.view === "session" ? (
          <SessionView cell={cell} sessionId={route.sessionId} turn={route.turn} turnView={route.turnView} />
        ) : (
          <SweepOverview index={index} />
        )}
      </main>
    </TooltipProvider>
  );
}
