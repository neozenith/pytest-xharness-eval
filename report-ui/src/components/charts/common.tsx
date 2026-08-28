/** The panel frame every chart shares: the glossary id on the root, the name beside the heading, an optional note. */
import { styled, Text, View, YStack } from "tamagui";
import { CardDescription, CardTitle } from "@/components/ui/card";
import { El } from "@/components/El";

/**
 * The label on a chart control. Its own step in the scale, between `CardTitle` (15/20, names a
 * section) and `CardDescription` (12.5/18 muted, explains one): the same size and measure as a
 * description so a control row keeps the caption rhythm, at full ink and heading weight because
 * it names the control beside it rather than commenting on it.
 */
export const ControlLabel = styled(Text, {
  name: "XhControlLabel",
  render: "span",
  color: "$color",
  fontFamily: "$body",
  fontSize: 12.5,
  lineHeight: 18,
  fontWeight: "600",
});

interface PanelProps {
  id: string;
  title: string;
  note?: React.ReactNode;
  children: React.ReactNode;
}

/**
 * A chart sits inside a `CardContent`, so it cannot use `CardHeader` — that would double the
 * card's own horizontal padding. It borrows the same title and description styles instead, so
 * a chart's heading is typographically the same object as a panel's: one size, one measure.
 */
export function ChartPanel({ id, title, note, children }: PanelProps) {
  return (
    <View render="section" id={id} data-el={id} flexDirection="column" gap={16}>
      <YStack gap={3}>
        <CardTitle>
          {title}
          <El name={id} />
        </CardTitle>
        {note ? <CardDescription>{note}</CardDescription> : null}
      </YStack>
      {children}
    </View>
  );
}
