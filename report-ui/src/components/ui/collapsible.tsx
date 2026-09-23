/**
 * Collapsible disclosure, built on Tamagui; keeps the radix-style Root/Trigger/Content
 * surface. Trigger text children are wrapped in a Text node — tamagui's dev mode reports a
 * raw text child as a console error whose payload (the whole fiber) is heavy enough to
 * crash the dev-server tab once vite's console forwarder serialises hundreds of them.
 *
 * Tamagui's trigger names its content in `aria-controls` but the content never renders that
 * id, so the reference dangled (WCAG 4.1.2). The wrapper owns one id, puts it on the content,
 * and points the trigger at it only while the content is mounted — closed, there is nothing
 * to control, and a reference to an absent node is the defect all over again.
 */
import { createContext, useContext, useId, useState, type ComponentProps } from "react";
import { Collapsible as TamaguiCollapsible } from "tamagui";
import { wrapTextChildren } from "./button";

const Disclosure = createContext<{ id: string; open: boolean } | undefined>(undefined);

export function Collapsible({ open, defaultOpen, onOpenChange, ...props }: ComponentProps<typeof TamaguiCollapsible>) {
  const id = useId();
  const [own, setOwn] = useState(defaultOpen ?? false);
  const current = open ?? own;
  const change = (next: boolean) => {
    if (open === undefined) setOwn(next);
    onOpenChange?.(next);
  };
  return (
    <Disclosure.Provider value={{ id, open: current }}>
      <TamaguiCollapsible {...props} open={current} onOpenChange={change} />
    </Disclosure.Provider>
  );
}

export function CollapsibleTrigger({ children, ...props }: ComponentProps<typeof TamaguiCollapsible.Trigger>) {
  const d = useContext(Disclosure);
  return (
    <TamaguiCollapsible.Trigger {...props} aria-controls={d?.open ? d.id : undefined}>
      {wrapTextChildren(children)}
    </TamaguiCollapsible.Trigger>
  );
}

export function CollapsibleContent(props: ComponentProps<typeof TamaguiCollapsible.Content>) {
  const d = useContext(Disclosure);
  return <TamaguiCollapsible.Content id={d?.id} {...props} />;
}
