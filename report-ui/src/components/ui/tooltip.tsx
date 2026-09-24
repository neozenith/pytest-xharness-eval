/**
 * Tooltips, built on Tamagui; keeps the radix-style Provider/Root/Trigger/Content surface.
 * Tamagui needs no provider, so `TooltipProvider` only passes children through (kept so
 * call sites and tests read the same).
 */
import { createContext, useCallback, useContext, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { Text, Tooltip as TamaguiTooltip, type TooltipProps } from "tamagui";

export function TooltipProvider({ children }: { children: ReactNode; delayDuration?: number }) {
  return <>{children}</>;
}

/*
 * Tamagui's tooltip wires a focus interaction, but it never fires through `Tooltip.Trigger`, so
 * a keyboard reader who tabbed to a trigger got no tooltip at all (WCAG 1.4.13 / 2.1.1). The
 * wrapper therefore owns the open state (controlled or not) and the trigger opens it on a
 * *keyboard* focus (`:focus-visible`, so a click does not pop it) and closes it on blur.
 * Escape and pointer-leave still arrive through Tamagui's `onOpenChange`. The content's id is
 * the wrapper's too (on its text), so the trigger is described by the tooltip however it was opened —
 * Tamagui only links the two for a hover.
 */
interface Shared {
  id: string;
  open: boolean;
  setOpen: (open: boolean) => void;
}
const Ctx = createContext<Shared | undefined>(undefined);

export function Tooltip({ open, onOpenChange, ...props }: TooltipProps) {
  const id = useId();
  const [own, setOwn] = useState(false);
  const current = open ?? own;
  // Latest props behind a stable function, so the trigger's listeners bind once.
  const latest = useRef({ open, onOpenChange });
  latest.current = { open, onOpenChange };
  const setOpen = useCallback((next: boolean) => {
    if (latest.current.open === undefined) setOwn(next);
    latest.current.onOpenChange?.(next);
  }, []);
  const shared = useMemo(() => ({ id, open: current, setOpen }), [id, current, setOpen]);
  return (
    <Ctx.Provider value={shared}>
      <TamaguiTooltip delay={200} restMs={150} placement="top" {...props} open={current} onOpenChange={setOpen} />
    </Ctx.Provider>
  );
}

type TriggerProps = Parameters<typeof TamaguiTooltip.Trigger>[0];

export function TooltipTrigger(props: TriggerProps) {
  const ctx = useContext(Ctx);
  const setOpen = ctx?.setOpen;
  const [node, setNode] = useState<HTMLElement | null>(null);
  /*
   * Native listeners on the trigger's own DOM node: a React `onFocus` handed to Tamagui's
   * trigger is dropped on the way through its anchor, the same path its own focus hook loses.
   */
  useEffect(() => {
    if (!node || !setOpen) return;
    const focus = () => {
      if (node.matches(":focus-visible")) setOpen(true);
    };
    const blur = () => setOpen(false);
    node.addEventListener("focus", focus);
    node.addEventListener("blur", blur);
    return () => {
      node.removeEventListener("focus", focus);
      node.removeEventListener("blur", blur);
    };
  }, [node, setOpen]);
  return <TamaguiTooltip.Trigger aria-describedby={ctx?.open ? ctx.id : undefined} {...props} ref={setNode as never} />;
}

export function TooltipContent({ children, className }: { children: ReactNode; className?: string }) {
  const id = useContext(Ctx)?.id;
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
      // Tamagui makes tooltip content click-through, so a pointer that moved onto a long
      // definition to read it fell through and closed it (WCAG 1.4.13: hoverable).
      pointerEvents="auto"
      boxShadow="0 4px 12px -2px var(--xh-shadow), 0 2px 4px -2px var(--xh-shadow)"
      transition="100ms"
      enterStyle={{ opacity: 0, y: 2 }}
      exitStyle={{ opacity: 0, y: 2 }}
    >
      {/* The id sits on the text, not the panel: Tamagui overwrites the panel's with its own. */}
      <Text id={id} color="$panel" fontSize={12} lineHeight={16} fontFamily="$body">
        {children}
      </Text>
    </TamaguiTooltip.Content>
  );
}
