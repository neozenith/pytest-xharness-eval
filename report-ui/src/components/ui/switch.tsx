/**
 * The toggle switch, built on Tamagui; keeps the radix-style `checked`/`onCheckedChange` surface.
 * The styling props sit *after* the spread on purpose: Tamagui applies props in insertion order.
 * The checked track is the one thing that still cannot be won that way — Tamagui's own `checked`
 * variant repaints it — so `.XhSwitch` in index.css pins it, like the other Tamagui overrides.
 */
import type { ComponentProps } from "react";
import { Switch as TamaguiSwitch } from "tamagui";

export function Switch({ className, ...props }: ComponentProps<typeof TamaguiSwitch>) {
  const on = Boolean(props.checked);
  return (
    <TamaguiSwitch
      size="$2"
      {...props}
      className={["XhSwitch", className].filter(Boolean).join(" ")}
      width={34}
      height={20}
      padding={2}
      cursor="pointer"
      // Off is a recessed slot, a shade deeper than the panel it sits on, so the knob reads as
      // a knob in a track rather than a filled dot floating on a card.
      backgroundColor={on ? "$accent" : "color-mix(in srgb, var(--xh-muted) 12%, var(--xh-code))"}
      borderWidth={1}
      borderColor={on ? "$accent" : "$line"}
      transition="100ms"
      hoverStyle={{ borderColor: on ? "$accent" : "color-mix(in srgb, var(--xh-muted) 45%, var(--xh-line))" }}
      focusVisibleStyle={{ outlineColor: "$accent", outlineStyle: "solid", outlineWidth: 2, outlineOffset: 2 }}
    >
      <TamaguiSwitch.Thumb
        width={14}
        height={14}
        borderRadius={999}
        borderWidth={0}
        // Off, the knob is muted pulled back toward the panel: it stays legible against the
        // track in both themes without the full-strength dot reading as an "on" state.
        backgroundColor={on ? "$panel" : "color-mix(in srgb, var(--xh-muted) 72%, var(--xh-panel))"}
        boxShadow="0 1px 2px var(--xh-shadow)"
        transition="200ms"
      />
    </TamaguiSwitch>
  );
}
