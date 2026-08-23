/**
 * The component's glossary name, rendered beside its heading so the page reads in the
 * vocabulary of XHARNESS-REPORT-GLOSSARY.md (ADR 0021). Every panel, table and card shows one.
 */
export function El({ name }: { name: string }) {
  return (
    <span className="el text-muted-foreground ml-2 font-mono text-[0.7rem] font-medium tracking-normal normal-case" data-el={name}>
      {name}
    </span>
  );
}
