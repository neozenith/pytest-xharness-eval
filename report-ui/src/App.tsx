import { useEffect, useMemo, useState } from "react";
import { TamaguiProvider, Text, Theme, View, XStack } from "tamagui";
import { config } from "@/tamagui.config";
import { TooltipProvider } from "@/components/ui/tooltip";
import { NavSidebar } from "@/components/NavSidebar";
import { ReportHeader } from "@/components/ReportHeader";
import { loadIndex, loadTokens } from "@/lib/data";
import { replaceRoute, useRoute } from "@/lib/route";
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

  // A `theme=` param forces the theme, so a shared link reproduces what the sender saw.
  const effectiveMode = route.theme ?? mode;

  useEffect(() => {
    if (tokens) applyTokens(tokens, effectiveMode);
    else document.documentElement.classList.toggle("dark", effectiveMode === "dark");
  }, [tokens, effectiveMode]);

  const toggleMode = () => {
    const next = effectiveMode === "dark" ? "light" : "dark";
    setMode(next);
    rememberMode(next);
    if (route.theme) replaceRoute({ ...route, theme: next });
  };

  const cell = useMemo(() => (route.view === "session" && index ? index.cells.find((c) => c.session_id === route.sessionId) : undefined), [route, index]);

  return (
    <TamaguiProvider config={config} defaultTheme={effectiveMode}>
      <Theme name={effectiveMode}>
        <TooltipProvider delayDuration={200}>
          <ReportHeader index={index} cell={cell} mode={effectiveMode} onToggleMode={toggleMode} />
          <XStack>
            <NavSidebar index={index} route={route} />
            <View render="main" marginHorizontal="auto" maxWidth={1600} minWidth={0} flexGrow={1} flexShrink={1} gap={16} padding={24}>
              {error ? (
                <Text render="p" color="$bad" fontFamily="$body" fontSize={14}>
                  {error}. The page fetches its data from beside itself: serve the cache directory over HTTP, or write it with{" "}
                  <code>--xharness-report-inline</code>.
                </Text>
              ) : !index ? (
                <Text render="p" color="$muted" fontFamily="$body" fontSize={14} data-xh-loading="index">
                  loading…
                </Text>
              ) : route.view === "session" ? (
                <SessionView cell={cell} route={route} />
              ) : (
                <SweepOverview index={index} />
              )}
            </View>
          </XStack>
        </TooltipProvider>
      </Theme>
    </TamaguiProvider>
  );
}
