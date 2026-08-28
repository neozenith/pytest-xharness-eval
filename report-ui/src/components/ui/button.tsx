/**
 * The page's button, built on Tamagui (base UI and animation framework). Same surface the
 * previous shadcn button exposed at the call sites: `variant`, `size`, plus `render={<a href/>}`
 * for link-shaped buttons (Tamagui's `render` replaces radix `asChild`). String children are
 * wrapped in a Text node — tamagui's dev mode reports a raw text child as a console error
 * (and vite's console forwarder serialising hundreds of those crashes the dev tab).
 */
import type { ComponentProps, ReactNode } from "react";
import { styled, Text, View } from "tamagui";

const ButtonFrame = styled(View, {
  name: "XhButton",
  render: "button",
  cursor: "pointer",
  flexDirection: "row",
  display: "inline-flex",
  alignSelf: "flex-start",
  alignItems: "center",
  justifyContent: "center",
  gap: 6,
  borderRadius: 8,
  borderWidth: 1,
  borderColor: "transparent",
  backgroundColor: "transparent",
  userSelect: "none",
  // Colour eases; the press scale snaps, which is what makes it feel like a button.
  transition: { default: "100ms", transform: "75ms" },
  pressStyle: { scale: 0.97 },
  focusVisibleStyle: { outlineColor: "$accent", outlineStyle: "solid", outlineWidth: 2, outlineOffset: 2 },

  variants: {
    variant: {
      /*
       * The raised variant: a hairline, a sliver of elevation off the card, and a press that
       * takes the elevation away as it scales — the shadow leaving is what sells the travel.
       */
      outline: {
        borderColor: "$line",
        backgroundColor: "$panel",
        boxShadow: "0 1px 2px -1px var(--xh-shadow)",
        hoverStyle: {
          backgroundColor: "$code",
          borderColor: "color-mix(in srgb, var(--xh-muted) 45%, var(--xh-line))",
          boxShadow: "0 2px 4px -2px var(--xh-shadow)",
        },
        pressStyle: { backgroundColor: "$code", scale: 0.97, boxShadow: "0 0 0 0 transparent" },
      },
      ghost: {
        hoverStyle: { backgroundColor: "$code" },
        pressStyle: { backgroundColor: "$code", scale: 0.97 },
      },
    },
    size: {
      // Heights climb the 4px rhythm; every one clears a 28px hit target except `xs`, which is
      // only ever a chip inside dense data.
      default: { height: 32, paddingHorizontal: 14 },
      sm: { height: 28, paddingHorizontal: 10 },
      xs: { height: 26, paddingHorizontal: 8, borderRadius: 6 },
      "icon-sm": { height: 32, width: 32, paddingHorizontal: 0 },
    },
  } as const,

  defaultVariants: { variant: "outline", size: "default" },
});

/**
 * Bare strings and numbers become a Text node that inherits every typographic property, so
 * it renders exactly as the raw text node did; anything else passes through untouched.
 */
export function wrapTextChildren(children: ReactNode): ReactNode {
  const inherit = { font: "inherit", color: "inherit", letterSpacing: "inherit", whiteSpace: "inherit" } as const;
  const wrap = (child: ReactNode, key?: number) =>
    typeof child === "string" || typeof child === "number" ? (
      <Text key={key} style={inherit}>
        {child}
      </Text>
    ) : (
      child
    );
  return Array.isArray(children) ? children.map((child, i) => wrap(child, i)) : wrap(children);
}

/** Typography per size, applied as plain CSS on the frame so the wrapped Text inherits it. */
const TYPE = {
  default: { fontSize: 13, lineHeight: "16px" },
  sm: { fontSize: 12.5, lineHeight: "16px" },
  xs: { fontSize: 11.5, lineHeight: "14px" },
  "icon-sm": { fontSize: 13, lineHeight: "16px" },
} as const;

export function Button({ children, ...props }: ComponentProps<typeof ButtonFrame>) {
  const type = TYPE[(props.size as keyof typeof TYPE) ?? "default"] ?? TYPE.default;
  return (
    <ButtonFrame {...props} style={{ fontWeight: 500, whiteSpace: "nowrap", ...type, ...(props.style as object) }}>
      {wrapTextChildren(children)}
    </ButtonFrame>
  );
}
