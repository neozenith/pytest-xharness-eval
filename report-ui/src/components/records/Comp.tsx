import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Every renderer of the record-card library wraps its output in one of these, named as the
 * glossary names it (`V.code`, `T.Bash`, `B.tool_use`, `claudeMessage`, `R.<kind>`,
 * `RecordCard`), so the rendered HTML itself says which component drew what. Empty output
 * renders nothing, as the legacy `comp()` did. Document content styles by index.css.
 */
export function Comp({ el, children, className }: { el: string; children?: ReactNode; className?: string }) {
  if (children == null || children === false || children === "") return null;
  if (Array.isArray(children) && children.every((c) => c == null || c === false || c === "")) return null;
  return (
    <div className={cn("comp", className)} data-el={el}>
      <span className="comp-label">{el}</span>
      {children}
    </div>
  );
}

export const Muted = ({ children }: { children: ReactNode }) => <span className="muted note">{children}</span>;
export const Notice = ({ children }: { children: ReactNode }) => <span className="warn note">{children}</span>;
export const Mono = ({ children }: { children: ReactNode }) => <code className="mono-sm">{children}</code>;
export const Tag = ({ children, tone }: { children: ReactNode; tone?: "added" | "removed" }) => <span className={cn("tag", tone)}>{children}</span>;
