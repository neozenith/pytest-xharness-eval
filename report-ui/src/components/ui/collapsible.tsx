/**
 * Collapsible disclosure, built on Tamagui; keeps the radix-style Root/Trigger/Content
 * surface. Trigger text children are wrapped in a Text node — tamagui's dev mode reports a
 * raw text child as a console error whose payload (the whole fiber) is heavy enough to
 * crash the dev-server tab once vite's console forwarder serialises hundreds of them.
 */
import type { ComponentProps } from "react";
import { Collapsible as TamaguiCollapsible } from "tamagui";
import { wrapTextChildren } from "./button";

export const Collapsible = TamaguiCollapsible;
export const CollapsibleContent = TamaguiCollapsible.Content;

export function CollapsibleTrigger({ children, ...props }: ComponentProps<typeof TamaguiCollapsible.Trigger>) {
  return <TamaguiCollapsible.Trigger {...props}>{wrapTextChildren(children)}</TamaguiCollapsible.Trigger>;
}
