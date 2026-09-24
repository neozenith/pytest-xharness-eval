import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { El } from "@/components/El";

/** The agent's final message: what the harness returned as the result. */
export function FinalMessagePanel({ text }: { text: string | null | undefined }) {
  return (
    <Card id="FinalMessagePanel" data-el="FinalMessagePanel">
      <CardHeader>
        <CardTitle>
          Final message
          <El name="FinalMessagePanel" />
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* Capped at 480px and scrolling, so it is a named tab stop (WCAG 2.1.1), as records/values.tsx `Pre` is. */}
        <pre id="FinalMessage" className="final-pre" tabIndex={0} role="region" aria-label="final message (scrollable)">
          {text || "(empty)"}
        </pre>
      </CardContent>
    </Card>
  );
}
