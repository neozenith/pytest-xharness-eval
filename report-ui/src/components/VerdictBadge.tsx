import { Badge } from "@/components/ui/badge";

const TOKEN: Record<string, "good" | "bad" | "warn"> = { pass: "good", fail: "bad" };

/** The history verdict as a pill: pass, fail, or "no history" when the line never landed. */
export function VerdictBadge({ verdict }: { verdict: string | null }) {
  const token = verdict ? (TOKEN[verdict] ?? "warn") : null;
  const tone = token ?? "outline";
  /*
   * Twenty-four rows of a sweep are mostly passes, so a pass keeps the kit's quiet 13% tint and
   * anything that is *not* a pass is raised a step — a fuller wash and a real border — because
   * it is the exception the eye has to find. Hue alone is not enough at 11px: two pills of
   * equal weight make you read every one of them.
   */
  const loud = token != null && verdict !== "pass";
  return (
    <Badge
      tone={tone}
      fontFamily="$mono"
      textTransform="uppercase"
      // One width for every verdict, so the column has a straight right edge to scan down.
      minWidth={54}
      {...(loud
        ? {
            backgroundColor: `color-mix(in srgb, var(--xh-${token}) 20%, transparent)`,
            borderColor: `color-mix(in srgb, var(--xh-${token}) 58%, transparent)`,
            fontWeight: "700" as const,
          }
        : null)}
    >
      {verdict ?? "no history"}
    </Badge>
  );
}
