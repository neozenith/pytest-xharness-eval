/** The panel card, built on Tamagui: the frame every chart, table and panel sits in. */
import { styled, Text, View } from "tamagui";

export const Card = styled(View, {
  name: "XhCard",
  render: "section",
  flexDirection: "column",
  backgroundColor: "$panel",
  borderColor: "$line",
  borderWidth: 1,
  borderRadius: 12,
  paddingVertical: 20,
  gap: 16,
  // A card is a surface, not a box: one hairline plus a shadow barely above the paper.
  // `--xh-shadow` is near-invisible in light and a real void in dark, so both themes read.
  boxShadow: "0 1px 2px -1px var(--xh-shadow), 0 8px 20px -12px var(--xh-shadow)",
  transition: "200ms",
  enterStyle: { opacity: 0, y: 4 },
});

export const CardHeader = styled(View, {
  name: "XhCardHeader",
  render: "header",
  flexDirection: "column",
  gap: 3,
  paddingHorizontal: 20,
});

export const CardTitle = styled(Text, {
  name: "XhCardTitle",
  render: "h2",
  color: "$color",
  fontFamily: "$body",
  fontSize: 15,
  lineHeight: 20,
  fontWeight: "600",
  letterSpacing: -0.1,
  margin: 0,
});

export const CardDescription = styled(Text, {
  name: "XhCardDescription",
  render: "p",
  color: "$muted",
  fontFamily: "$body",
  fontSize: 12.5,
  lineHeight: 18,
  maxWidth: "78ch",
  margin: 0,
});

export const CardContent = styled(View, {
  name: "XhCardContent",
  flexDirection: "column",
  paddingHorizontal: 20,
});
