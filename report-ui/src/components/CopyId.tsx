import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { styled, Text, XStack } from "tamagui";

const CopyFrame = styled(XStack, {
  name: "XhCopyId",
  render: "button",
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  // The kit's 20px chip tier — the one rule index.css's "chips and pills" block actually
  // states. At 28px this sat immediately left of a 20px VerdictBadge in every SessionTable
  // row, and two chips a row apart in height read as a misalignment rather than a scale.
  minHeight: 20,
  borderRadius: 5,
  paddingHorizontal: 6,
  paddingVertical: 0,
  // No resting fill. Twenty-four filled slabs running down the first column were the heaviest
  // mark on the page and out-competed the verdict pills beside them, which are what should
  // lead a row. The surface arrives on hover and focus, where it is an affordance rather than
  // decoration; the copy glyph carries the "copyable" signal at rest.
  backgroundColor: "transparent",
  // An id is one token: it must never wrap, or the chip goes two lines tall and takes the
  // whole table row's height with it.
  flexShrink: 0,
  cursor: "pointer",
  transition: "100ms",
  // `$line`, not `$code`: pointing at a chip also hovers its row, and the row's own wash sits
  // at almost exactly `$code`'s value — the chip would light up into invisibility.
  hoverStyle: { backgroundColor: "$line" },
  // The page's shared ring is drawn 2px *outside* its target, and the SessionTable's scroll
  // box clips anything an outline puts past its edges — a chip in the first or last column
  // lost a side of its ring. Inboard, like the row's and the header's, so every side stays on.
  focusVisibleStyle: { backgroundColor: "$line", outlineColor: "$accent", outlineStyle: "solid", outlineWidth: 2, outlineOffset: -1 },
  // A copy is a small physical act; the chip gives under the press and comes straight back.
  pressStyle: { scale: 0.97 },
});

/** A session id rendered short, copied whole on click. */
export function CopyId({ id, label }: { id: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const [lit, setLit] = useState(false);
  const copy = async (e: { stopPropagation: () => void }) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      /* clipboard unavailable over plain http: the title still shows the full id */
    }
  };
  return (
    <CopyFrame
      render={
        <button
          type="button"
          title={id}
          aria-label={`Copy ${id}`}
          onMouseEnter={() => setLit(true)}
          onMouseLeave={() => setLit(false)}
          onFocus={() => setLit(true)}
          onBlur={() => setLit(false)}
        />
      }
      onPress={copy}
    >
      {/* 12/16, the `.code-chip` line box: the font's own 24px default alone made the chip 24px. */}
      <Text fontFamily="$mono" fontSize={12} lineHeight={16} color="$color" whiteSpace="nowrap" flexShrink={0}>
        {label ?? id}
      </Text>
      {/*
       * Two dozen of these run down the first column of the SessionTable, so the glyph rests
       * at a third strength and comes up to full on hover or focus: enough to say "copyable"
       * from a distance, not enough to compete with the ids themselves. It keeps its box at
       * every strength, so nothing reflows when it lights up or flips to the tick.
       */}
      <Text display="inline-flex" color={copied ? "$good" : "$color"} opacity={copied || lit ? 1 : 0.35} transition="100ms">
        {copied ? <Check size={12} aria-hidden /> : <Copy size={12} aria-hidden />}
      </Text>
    </CopyFrame>
  );
}
