/**
 * Tooltips, built on Tamagui; keeps the radix-style Provider/Root/Trigger/Content surface.
 * Tamagui needs no provider, so `TooltipProvider` only passes children through (kept so
 * call sites and tests read the same).
 */
import type { ReactNode } from "react";
import { Text, Tooltip as TamaguiTooltip, type TooltipProps } from "tamagui";

export function TooltipProvider({ children }: { children: ReactNode; delayDuration?: number }) {
  return <>{children}</>;
}

export function Tooltip(props: TooltipProps) {
  return <TamaguiTooltip delay={200} restMs={150} placement="top" {...props} />;
}

export const TooltipTrigger = TamaguiTooltip.Trigger;

export function TooltipContent({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <TamaguiTooltip.Content
      className={className}
      backgroundColor="$color"
      borderRadius={7}
      paddingHorizontal={10}
      paddingVertical={6}
      // Without an explicit `max-content`, the popper shrink-wraps to its narrowest possible
      // box and every tooltip renders one word per line; `maxWidth` then caps the long ones.
      width="max-content"
      maxWidth={280}
      zIndex={100}
      boxShadow="0 4px 12px -2px var(--xh-shadow), 0 2px 4px -2px var(--xh-shadow)"
      transition="100ms"
      enterStyle={{ opacity: 0, y: 2 }}
      exitStyle={{ opacity: 0, y: 2 }}
    >
      <Text color="$panel" fontSize={12} lineHeight={16} fontFamily="$body">
        {children}
      </Text>
    </TamaguiTooltip.Content>
  );
}
