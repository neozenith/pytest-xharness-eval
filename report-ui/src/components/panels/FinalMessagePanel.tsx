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
        <pre id="FinalMessage" className="final-pre">
          {text || "(empty)"}
        </pre>
      </CardContent>
    </Card>
  );
}
