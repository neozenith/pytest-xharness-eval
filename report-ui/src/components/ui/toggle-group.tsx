/**
 * The segmented single-choice control, built on Tamagui; keeps the radix-style
 * `type`/`value`/`onValueChange` surface the call sites use.
 *
 * Two things Tamagui's single-mode group does not do, and this wrapper does:
 *
 *   - it strips `aria-pressed` from every item, so the selection lived only in `data-state`
 *     and a screen reader could not tell which segment was chosen (WCAG 4.1.2);
 *   - it gives every item `tabIndex=0`, so the control cost one Tab stop per segment even
 *     though the arrow keys already rove between them.
 *
 * Both need the item to know the group's value, so the wrapper holds it (controlled or not)
 * and hands it down on a context. The selected segment is the one Tab stop; with nothing
 * selected (or the selected one disabled) it is the first enabled segment.
 *
 * The group frame itself is taken out of the tab order. Tamagui's RovingFocusGroup makes it a
 * stop once its items register, and forwards focus to a segment with `focusVisible: false` —
 * so the first Tab into a settled control landed on a segment with no focus ring at all.
 */
import { Children, createContext, isValidElement, useContext, useState, type ReactNode } from "react";
import { ToggleGroup as TamaguiToggleGroup, type ToggleGroupSingleProps, type ToggleGroupItemProps } from "tamagui";
import { wrapTextChildren } from "./button";

type GroupProps = Omit<ToggleGroupSingleProps, "type"> & {
  type?: "single";
  /** accepted for call-site compatibility; the look is the report's own */
  variant?: string;
  size?: string;
};

/** The group's current value, and the one segment that holds the Tab stop. */
const Selected = createContext<{ value: string; stop: string | undefined }>({ value: "", stop: undefined });

/** The selected segment if it is enabled, else the first enabled one. */
function tabStop(children: ReactNode, value: string): string | undefined {
  const items = Children.toArray(children)
    .filter(isValidElement)
    .map((child) => child.props as { value?: string; disabled?: boolean })
    .filter((item) => item.value !== undefined && !item.disabled);
  return (items.find((item) => item.value === value) ?? items[0])?.value;
}

export function ToggleGroup({ type: _type, variant: _variant, size: _size, className, value, defaultValue, onValueChange, ...props }: GroupProps) {
  const [own, setOwn] = useState(defaultValue ?? "");
  const current = value ?? own;
  const change = (next: string) => {
    if (value === undefined) setOwn(next);
    onValueChange?.(next);
  };
  // `.XhToggleGroup [data-state="on"]` in index.css paints the selected segment.
  return (
    <Selected.Provider value={{ value: current, stop: tabStop(props.children, current) }}>
      <TamaguiToggleGroup
        type="single"
        orientation="horizontal"
        className={["XhToggleGroup", className].filter(Boolean).join(" ")}
        {...props}
        tabIndex={-1}
        value={current}
        onValueChange={change}
      />
    </Selected.Provider>
  );
}

export function ToggleGroupItem({ children, ...props }: ToggleGroupItemProps) {
  const group = useContext(Selected);
  const selected = group.value === props.value;
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
      aria-pressed={selected}
      tabIndex={group.stop === props.value ? 0 : -1}
    >
      {wrapTextChildren(children)}
    </TamaguiToggleGroup.Item>
  );
}
