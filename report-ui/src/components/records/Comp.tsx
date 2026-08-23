import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Every renderer of the record-card library wraps its output in one of these, named as the
 * glossary names it (`V.code`, `T.Bash`, `B.tool_use`, `claudeMessage`, `R.<kind>`,
 * `RecordCard`), so the rendered HTML itself says which component drew what. Empty output
 * renders nothing, as the legacy `comp()` did.
 */
export function Comp({ el, children, className }: { el: string; children?: ReactNode; className?: string }) {
  if (children == null || children === false || children === "") return null;
  if (Array.isArray(children) && children.every((c) => c == null || c === false || c === "")) return null;
  return (
    <div className={cn("comp relative", className)} data-el={el}>
      <span className="comp-label text-muted-foreground pointer-events-none absolute top-0 right-1 z-[1] font-mono text-[0.6rem] leading-snug font-medium opacity-75">
        {el}
      </span>
      {children}
    </div>
  );
}

export const Muted = ({ children }: { children: ReactNode }) => <span className="text-muted-foreground text-sm">{children}</span>;
export const Notice = ({ children }: { children: ReactNode }) => <span className="text-warn text-sm">{children}</span>;
export const Mono = ({ children }: { children: ReactNode }) => <code className="font-mono text-[0.8rem]">{children}</code>;
export const Tag = ({ children, tone }: { children: ReactNode; tone?: "added" | "removed" }) => (
  <span
    className={cn(
      "bg-muted text-muted-foreground inline-block rounded-[5px] border px-[0.45rem] font-mono text-[0.72rem]",
      tone === "added" && "text-good",
      tone === "removed" && "text-bad",
    )}
  >
    {children}
  </span>
);
