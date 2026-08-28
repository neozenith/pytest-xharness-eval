import { Moon, Sun } from "lucide-react";
import { Text, View, XStack } from "tamagui";
import { Button } from "@/components/ui/button";
import { El } from "@/components/El";
import { short, usd, when } from "@/lib/format";
import { navigateOnClick } from "@/lib/route";
import type { Mode } from "@/lib/tokens";
import type { Cell, Index } from "@/lib/types";

interface Props {
  index: Index | null;
  cell: Cell | undefined;
  mode: Mode;
  onToggleMode: () => void;
}

const Sep = () => (
  <Text color="$muted" fontWeight="400">
    ·
  </Text>
);

/**
 * The page header. On the sweep the title is the report's; inside a SessionView it is the
 * eval · session · harness · model tuple, so the tab and the top line say where you are.
 */
export function ReportHeader({ index, cell, mode, onToggleMode }: Props) {
  const total = index ? index.cells.reduce((s, c) => s + (c.estimated_cost_usd ?? 0), 0) : 0;
  // A sweep can span several skills; the header names them so no session's subject is invisible.
  const skills = index ? [...new Set(index.cells.map((c) => c.skill).filter((s): s is string => Boolean(s)))].sort() : [];
  return (
    <XStack
      render="header"
      id="ReportHeader"
      position="sticky"
      top={0}
      zIndex={10}
      alignItems="center"
      columnGap={16}
      rowGap={8}
      paddingHorizontal={24}
      paddingVertical={12}
      backgroundColor="$panel"
      borderBottomWidth={1}
      borderBottomColor="$line"
      borderStyle="solid"
    >
      <XStack render={<h1 id="ReportTitle" />} alignItems="baseline" gap={8} margin={0} flexShrink={0}>
        <Text
          render={<a href="?" onClick={navigateOnClick("?")} />}
          fontFamily="$body"
          fontSize={18}
          fontWeight="700"
          color="$color"
          hoverStyle={{ textDecorationLine: "underline" }}
        >
          {cell ? "xharness" : "xharness eval report"}
        </Text>
        {cell ? (
          <>
            <Text color="$muted">›</Text>
            <Text fontFamily="$body" fontSize={18} fontWeight="700">
              {cell.case}
            </Text>
            <Sep />
            <Text fontFamily="$mono" fontSize={16}>
              {short(cell.session_id)}
            </Text>
            <Sep />
            <Text fontFamily="$body" fontSize={18} fontWeight="700">
              {cell.harness}
            </Text>
            <Sep />
            <Text fontFamily="$mono" fontSize={16}>
              {cell.model}
            </Text>
          </>
        ) : null}
        <El name="ReportTitle" />
      </XStack>
      <Text render={<span id="ReportMeta" />} color="$muted" fontFamily="$body" fontSize={14} flexShrink={1} minWidth={0} className="truncate">
        {index ? (
          <>
            {index.cells.length} session(s)
            {skills.length ? ` · ${skills.length === 1 ? "skill" : `${skills.length} skills`}: ${skills.join(", ")}` : ""} · estimated {usd(total)} · generated{" "}
            {when(index.generated_at)}
            {index.inline ? " · inline" : ""}
          </>
        ) : (
          "loading…"
        )}
      </Text>
      <View flexGrow={1} />
      <Button
        id="ThemeToggle"
        variant="outline"
        size="icon-sm"
        onClick={onToggleMode}
        render={<button type="button" title="toggle light / dark" />}
        aria-label="toggle light / dark"
      >
        {mode === "dark" ? <Sun size={16} /> : <Moon size={16} />}
      </Button>
    </XStack>
  );
}
