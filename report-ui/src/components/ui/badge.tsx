/** The pill badge, built on Tamagui; `tone` colours it from the design tokens. */
import { styled, Text } from "tamagui";

/**
 * Tone is carried by a tint plus ink of the same hue, never a solid slab: sixteen solid
 * verdict pills stacked down a table column drown the data they annotate, and ink-on-tint
 * clears AA in both themes for every semantic colour (solid `warn` did not).
 */
const tint = (token: string) => ({
  backgroundColor: `color-mix(in srgb, var(--xh-${token}) 13%, transparent)`,
  borderColor: `color-mix(in srgb, var(--xh-${token}) 32%, transparent)`,
  color: `var(--xh-${token})`,
});

export const Badge = styled(Text, {
  name: "XhBadge",
  render: "span",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  borderRadius: 999,
  borderWidth: 1,
  borderColor: "transparent",
  paddingHorizontal: 8,
  height: 20,
  fontSize: 11,
  lineHeight: 18,
  fontWeight: "600",
  letterSpacing: 0.3,
  whiteSpace: "nowrap",

  variants: {
    tone: {
      good: tint("good"),
      bad: tint("bad"),
      warn: tint("warn"),
      accent: tint("accent"),
      outline: { borderColor: "$line", color: "$muted", backgroundColor: "transparent" },
    },
  } as const,

  defaultVariants: { tone: "outline" },
});
