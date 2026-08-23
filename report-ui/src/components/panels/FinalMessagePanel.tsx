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
        <pre id="FinalMessage" className="bg-muted max-h-[480px] overflow-auto rounded-md p-3 font-mono text-xs whitespace-pre-wrap">
          {text || "(empty)"}
        </pre>
      </CardContent>
    </Card>
  );
}
