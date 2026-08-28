/**
 * The one Plotly mount point (every chart goes through it) and the HTML legend the charts
 * share. The legend is DOM, not Plotly: it wraps in flexbox instead of overflowing the
 * card, themes with CSS, and toggles a series by re-rendering the plot with that trace set
 * to `legendonly`.
 */
import Plotly from "plotly.js-basic-dist-min";
import type { Config, Data, Layout } from "plotly.js";
import { useCallback, useEffect, useRef, useState } from "react";
import { Text, View, XStack, YStack } from "tamagui";

const CONFIG: Partial<Config> = { displayModeBar: false, responsive: true };

interface PlotProps {
  data: Data[];
  layout: Partial<Layout>;
  /** Chart height in px; the container reserves it so the page never reflows. */
  height: number;
  ariaLabel: string;
}

export function Plot({ data, layout, height, ariaLabel }: PlotProps) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    void Plotly.react(el, data, { ...layout, height }, CONFIG);
  }, [data, layout, height]);
  useEffect(() => {
    const el = ref.current;
    return () => {
      if (el) Plotly.purge(el);
    };
  }, []);
  return <div ref={ref} role="img" aria-label={ariaLabel} style={{ width: "100%", height }} />;
}

export interface LegendItem {
  key: string;
  label: string;
  color: string;
}

/** Which series are toggled off; the set is keyed by the legend item's `key`. */
export function useHiddenSeries(): { hidden: ReadonlySet<string>; toggle: (key: string) => void } {
  const [hidden, setHidden] = useState<ReadonlySet<string>>(new Set());
  const toggle = (key: string) =>
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  return { hidden, toggle };
}

interface LegendProps {
  items: LegendItem[];
  hidden?: ReadonlySet<string>;
  onToggle?: (key: string) => void;
  /** Match the chart's height so a long legend scrolls beside it instead of stretching the card. */
  maxHeight?: number;
}

/** Length of the fade ramp on a clipped legend edge; the same 28px the tables use. */
const RAMP = 28;

/**
 * A capped legend clips silently — the scrollbar only appears once you already guessed there
 * was more. The clipped edge fades its own chips out instead, so a half-shown chip cannot be
 * mistaken for the last one. Both ramps stay at zero until there is real overflow to signal.
 */
function useScrollEdges(deps: unknown[]): { attach: (node: unknown) => void; edges: { start: boolean; end: boolean } } {
  const ref = useRef<HTMLElement | null>(null);
  const [edges, setEdges] = useState({ start: false, end: false });
  // Tamagui types its ref as `TamaguiElement`; on the web that is the DOM node this measures.
  const attach = useCallback((node: unknown) => {
    ref.current = (node as HTMLElement | null) ?? null;
  }, []);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () =>
      setEdges((prev) => {
        const next = { start: el.scrollTop > 1, end: el.scrollTop + el.clientHeight < el.scrollHeight - 1 };
        return prev.start === next.start && prev.end === next.end ? prev : next;
      });
    measure();
    el.addEventListener("scroll", measure, { passive: true });
    // Guarded: the render tests run in jsdom, which has no ResizeObserver. Without one the
    // ramps simply never re-measure, which is the same as a legend that never overflowed.
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    observer?.observe(el);
    return () => {
      el.removeEventListener("scroll", measure);
      observer?.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { attach, edges };
}

/** The right-hand legend column: one chip per series, stacked, scrolling past `maxHeight`. */
export function ChartLegend({ items, hidden, onToggle, maxHeight }: LegendProps) {
  const { attach, edges } = useScrollEdges([items.length, maxHeight]);
  if (!items.length) return null;
  const mask = `linear-gradient(to bottom, transparent 0, black ${edges.start ? RAMP : 0}px, black calc(100% - ${edges.end ? RAMP : 0}px), transparent 100%)`;
  return (
    <YStack
      ref={attach}
      width={240}
      flexShrink={0}
      // On the 4px rhythm, and the clearance the outward focus ring needs: the ring reaches 3px
      // (2px outline, 1px offset), so a focused chip clears its neighbour's box by 1px instead
      // of drawing its bottom stroke inside it.
      gap={4}
      alignSelf="center"
      maxHeight={maxHeight}
      // The chips are inset from the clip box by the width of their focus ring (2px outline,
      // 1px offset): a scroll container clips its children, so without this gutter the ring on
      // the first and last chip loses the edge it is drawn on.
      padding={3}
      data-el="ChartLegend"
      style={{
        overflowY: "auto",
        overflowX: "hidden",
        overscrollBehaviorY: "contain",
        scrollbarWidth: "thin",
        scrollbarColor: "color-mix(in srgb, var(--xh-muted) 32%, transparent) transparent",
        WebkitMaskImage: mask,
        maskImage: mask,
      }}
    >
      {items.map((item) => {
        const off = hidden?.has(item.key) ?? false;
        return (
          <XStack
            key={item.key}
            render={<button type="button" title={onToggle ? `toggle ${item.label}` : undefined} />}
            aria-pressed={!off}
            onPress={onToggle ? () => onToggle(item.key) : undefined}
            display="inline-flex"
            // A sweep label wraps to two lines; the swatch stays on the first, where a bullet
            // belongs, instead of floating between them.
            alignItems="flex-start"
            minHeight={28}
            gap={8}
            borderRadius={6}
            paddingHorizontal={8}
            paddingVertical={6}
            backgroundColor="transparent"
            cursor={onToggle ? "pointer" : "default"}
            transition="100ms"
            // A chip is a hoverable row, so it takes the table's recipe: a wash of the muted ink
            // rather than the flat `code` surface. It composites over whatever the chip sits on
            // and lands at the same perceived strength in both themes, and press reads as a
            // clear step past hover instead of the hairline apart the two flat tokens were.
            hoverStyle={onToggle ? { backgroundColor: "color-mix(in srgb, var(--xh-muted) 10%, transparent)" } : undefined}
            pressStyle={onToggle ? { backgroundColor: "color-mix(in srgb, var(--xh-muted) 18%, transparent)" } : undefined}
            focusVisibleStyle={onToggle ? { outlineColor: "$accent", outlineStyle: "solid", outlineWidth: 2, outlineOffset: 1 } : undefined}
          >
            {/*
             * Toggled off, the swatch empties to an outline of its own series colour: a shape
             * change, so the state survives a colour-blind read and a greyscale print.
             */}
            <View
              aria-hidden
              width={10}
              height={10}
              flexShrink={0}
              borderRadius={3}
              // (16px line box − 10px swatch) / 2: optically centred on the first line of text.
              marginTop={3}
              style={{
                background: off ? "transparent" : item.color,
                // On: a wash of the muted ink, not `line`. A swatch is a graphical object you
                // need to read the chart, so a series colour close to the panel (the dark
                // `cache read` slate) must still carry an edge; `line` measured 1.3:1 against
                // the panel in both themes, which defined nothing.
                boxShadow: `inset 0 0 0 ${off ? 1.5 : 1}px ${off ? item.color : "color-mix(in srgb, var(--xh-muted) 45%, transparent)"}`,
              }}
            />
            <Text fontFamily="$body" fontSize={12} lineHeight={16} fontWeight="500" textAlign="left" color={off ? "$muted" : "$color"} userSelect="none">
              {item.label}
            </Text>
          </XStack>
        );
      })}
    </YStack>
  );
}

interface PlotWithLegendProps extends PlotProps, LegendProps {}

/** The chart with its legend on the right; the legend wraps below only when the row gets too narrow. */
export function PlotWithLegend({ data, layout, height, ariaLabel, items, hidden, onToggle }: PlotWithLegendProps) {
  return (
    <XStack flexWrap="wrap" alignItems="flex-start" columnGap={16} rowGap={12}>
      <View minWidth={320} flexGrow={1} flexShrink={1} flexBasis={0}>
        <Plot data={data} layout={layout} height={height} ariaLabel={ariaLabel} />
      </View>
      <ChartLegend items={items} hidden={hidden} onToggle={onToggle} maxHeight={height} />
    </XStack>
  );
}
