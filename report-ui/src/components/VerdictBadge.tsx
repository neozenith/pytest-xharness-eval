import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/** The history verdict as a pill: pass, fail, or "no history" when the line never landed. */
export function VerdictBadge({ verdict }: { verdict: string | null }) {
  const tone = verdict === "pass" ? "bg-good text-white" : verdict === "fail" ? "bg-bad text-white" : verdict ? "bg-warn text-white" : "";
  return (
    <Badge variant={verdict ? "default" : "outline"} className={cn("font-mono uppercase", tone)}>
      {verdict ?? "no history"}
    </Badge>
  );
}
