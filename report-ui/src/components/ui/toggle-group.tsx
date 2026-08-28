/**
 * The segmented single-choice control, built on Tamagui; keeps the radix-style
 * `type`/`value`/`onValueChange` surface the call sites use.
 */
import { ToggleGroup as TamaguiToggleGroup, type ToggleGroupSingleProps, type ToggleGroupItemProps } from "tamagui";
import { wrapTextChildren } from "./button";

type GroupProps = Omit<ToggleGroupSingleProps, "type"> & {
  type?: "single";
  /** accepted for call-site compatibility; the look is the report's own */
  variant?: string;
  size?: string;
};

export function ToggleGroup({ type: _type, variant: _variant, size: _size, className, ...props }: GroupProps) {
  // `.XhToggleGroup [data-state="on"]` in index.css paints the selected segment.
  return <TamaguiToggleGroup type="single" orientation="horizontal" className={["XhToggleGroup", className].filter(Boolean).join(" ")} {...props} />;
}

export function ToggleGroupItem({ children, ...props }: ToggleGroupItemProps) {
  // Weight stays 500 in both states on purpose: bolding the selected segment would resize
  // it and make the whole control twitch on every toggle.
  return (
    <TamaguiToggleGroup.Item
      width="auto"
      // 28 clears the hit-target floor and, with the track's 2px inset, gives a concentric
      // 7-inside-9 radius pair rather than the thumb looking rounder than the slot it sits in.
      height={28}
      paddingHorizontal={11}
      borderWidth={0}
      borderRadius={7}
      backgroundColor="transparent"
      transition="100ms"
      // Segment typography, and every per-state surface including hover, are
      // `.XhToggleGroup …` in index.css: Tamagui's item is a View frame, whose props reject
      // type styling outright, and it has no way to know which segment is the selected one.
      // A `hoverStyle` here would only emit an atomic class the stylesheet has to outrank.
      focusVisibleStyle={{ outlineColor: "$accent", outlineStyle: "solid", outlineWidth: 2, outlineOffset: -1 }}
      {...props}
    >
      {wrapTextChildren(children)}
    </TamaguiToggleGroup.Item>
  );
}
