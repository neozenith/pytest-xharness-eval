/**
 * V: the value-level renderers of the record-card library (glossary: "How a RecordCard is
 * rendered", level *values*). Each is a component whose root is `<Comp el="V.<name>">`.
 * `json`, `bash` and `diff` draw through the unlabelled `CodeBlock` so they carry one
 * label, not two, as the legacy `rawCode` did.
 */
import { AnsiUp } from "ansi_up";
import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { fmt } from "@/lib/format";
import { CATEGORIES } from "@/lib/records";
import { Comp, Mono } from "./Comp";
import { ensureTheme, highlight } from "./hljs";

export { extLang } from "./hljs";

/**
 * The colour of a record category, as the page paints it: the project's `--xh-category-*`
 * token when `lib/tokens` has set one, otherwise the catalogue's own value. Every surface that
 * carries a category — the head's pill, a block's left rule — draws from this one function, so
 * an overridden palette moves them together instead of leaving a rule on a stale literal.
 */
export const categoryColour = (category: string): string => `var(--xh-category-${category}, ${CATEGORIES[category] ?? CATEGORIES.unknown})`;

export const pretty = (v: unknown): string => (typeof v === "string" ? v : JSON.stringify(v, null, 1));

// eslint-disable-next-line no-control-regex
export const hasAnsi = (s: unknown): boolean => /\x1b\[/.test(String(s ?? ""));

const ansiUp = new AnsiUp();

/** `[key, value]` pairs; a pair whose value is undefined, null or '' is dropped. */
export type Pair = [string, ReactNode | undefined | null];

const present = (v: ReactNode | undefined | null): boolean => v !== undefined && v !== null && v !== "";

/** The top edge of a code block: what it is on the left, what language it is set in on the right. */
const CodeHead = ({ title, lang }: { title?: string; lang?: string }) =>
  title ? (
    <div className="code-head">
      <span className="ch-title">{title}</span>
      {lang ? <span className="ch-lang">{lang}</span> : null}
    </div>
  ) : null;

/**
 * The scroll box every code-like value is set in. `.xh-pre` caps itself at 60vh and scrolls,
 * and a scrollable region that cannot be focused is a region a keyboard cannot read (WCAG
 * 2.1.1), so it takes the tab order and an accessible name — its own title and language, the
 * two things the head above it shows a pointer.
 */
const Pre = ({ children, className, label }: { children: ReactNode; className?: string; label?: string }) => (
  <pre className={`xh-pre ${className ?? ""}`} tabIndex={0} role="region" aria-label={label ? `${label} (scrollable)` : "code (scrollable)"}>
    {children}
  </pre>
);

/** The accessible name of a code block: what it is, and what it is set in. */
const preLabel = (title?: string, lang?: string): string => [title, lang].filter(Boolean).join(" · ") || "code";

/** Terminal output with colour codes, rendered in colour through ansi_up; nothing is stripped. */
export function Ansi({ text, title }: { text: unknown; title?: string }) {
  const html = ansiUp.ansi_to_html(String(text));
  return (
    <Comp el="V.ansi">
      <CodeHead title={title} lang="ansi" />
      <Pre label={preLabel(title, "ansi")}>
        <code className="ansi" dangerouslySetInnerHTML={{ __html: html }} />
      </Pre>
    </Comp>
  );
}

/** The unlabelled code block every code-like value shares. */
function CodeBlock({ lang, text, title }: { lang: string; text: unknown; title?: string }) {
  const src = typeof text === "string" ? text : pretty(text);
  if (hasAnsi(src)) return <Ansi text={src} title={title} />;
  ensureTheme();
  const html = highlight(lang, src);
  return (
    <>
      <CodeHead title={title} lang={lang || undefined} />
      <Pre className="xh-code" label={preLabel(title, lang)}>
        {html == null ? (
          <code className={`hljs language-${lang || "text"}`}>{src}</code>
        ) : (
          <code className={`hljs language-${lang}`} dangerouslySetInnerHTML={{ __html: html }} />
        )}
      </Pre>
    </>
  );
}

export function Text({ text }: { text: unknown }) {
  if (text == null || text === "") return null;
  if (hasAnsi(text)) return <Ansi text={text} />;
  return (
    <Comp el="V.text">
      <div className="txt">{String(text)}</div>
    </Comp>
  );
}

export function Kvs({ pairs }: { pairs: Pair[] }) {
  const rows = pairs.filter(([, v]) => present(v));
  if (!rows.length) return null;
  return (
    <Comp el="V.kvs">
      <div className="kvs">
        {rows.map(([k, v]) => (
          <div key={k} style={{ display: "contents" }}>
            <b>{k}</b>
            <span className="val">{v}</span>
          </div>
        ))}
      </div>
    </Comp>
  );
}

export function Code({ lang, text, title }: { lang: string; text: unknown; title?: string }) {
  return (
    <Comp el="V.code">
      <CodeBlock lang={lang} text={text} title={title} />
    </Comp>
  );
}

export const Json = ({ value, title }: { value: unknown; title?: string }) => (
  <Comp el="V.json">
    <CodeBlock lang="json" text={pretty(value)} title={title} />
  </Comp>
);

export const Bash = ({ cmd, title }: { cmd: unknown; title?: string }) => (
  <Comp el="V.bash">
    <CodeBlock lang="bash" text={cmd} title={title} />
  </Comp>
);

export const Diff = ({ text, title }: { text: unknown; title?: string }) => (
  <Comp el="V.diff">
    <CodeBlock lang="diff" text={text} title={title} />
  </Comp>
);

/** A collapsed section; renders nothing when there is nothing inside, as the legacy did. */
export function Details({ summary, children }: { summary: string; children?: ReactNode }) {
  if (children == null || children === false || children === "") return null;
  return (
    <Comp el="V.details">
      <Collapsible>
        <CollapsibleTrigger className="env-trigger">
          <ChevronRight className="chev" size={12} />
          {summary}
        </CollapsibleTrigger>
        <CollapsibleContent>{children}</CollapsibleContent>
      </Collapsible>
    </Comp>
  );
}

/** A boolean as a check or cross; any other value as text. Not wrapped: it is a glyph, not a component. */
export function Flag({ value }: { value: unknown }) {
  if (value === true)
    return (
      <>
        <span className="good">✓</span> true
      </>
    );
  if (value === false)
    return (
      <>
        <span className="muted">✗</span> false
      </>
    );
  return <>{String(value)}</>;
}

/** A vendor usage object (either dialect) as a token grid. */
export function Usage({ usage }: { usage: unknown }) {
  if (!usage || typeof usage !== "object") return null;
  const u = usage as Record<string, unknown>;
  const num = (v: unknown): number | null => (typeof v === "number" ? v : null);
  const creation = u.cache_creation as Record<string, unknown> | undefined;
  const details = u.output_tokens_details as Record<string, unknown> | undefined;
  return (
    <Comp el="V.usage">
      <Kvs
        pairs={[
          ["input", fmt(num(u.input_tokens))],
          ["cache read", fmt(num(u.cache_read_input_tokens ?? u.cached_input_tokens))],
          ["cache write", fmt(num(u.cache_creation_input_tokens ?? u.cache_write_input_tokens))],
          ["1h / 5m", creation ? `${fmt(num(creation.ephemeral_1h_input_tokens))} / ${fmt(num(creation.ephemeral_5m_input_tokens))}` : undefined],
          ["output", fmt(num(u.output_tokens))],
          ["thinking", fmt(num(details?.thinking_tokens ?? u.reasoning_output_tokens))],
          ["total", u.total_tokens != null ? fmt(num(u.total_tokens)) : undefined],
        ]}
      />
    </Comp>
  );
}

/** The parsed value, or undefined when the text is not JSON. */
const tryJson = (t: string): unknown => {
  try {
    return JSON.parse(t);
  } catch {
    return undefined;
  }
};
const looksJson = (t: string): boolean => (t.startsWith("{") || t.startsWith("[")) && t.endsWith(t.startsWith("{") ? "}" : "]");
const looksDiff = (t: string): boolean => /^(@@ |diff --git |\*\*\* (Begin|Update|Add|Delete) )/m.test(t) || (/^--- /m.test(t) && /^\+\+\+ /m.test(t));

/** Tool output: sniffed as JSON, a diff, ANSI or plain text. */
export function Output({ text, title }: { text: unknown; title?: string }) {
  if (text == null || text === "") return null;
  if (hasAnsi(text))
    return (
      <Comp el="V.output">
        <Ansi text={text} title={title} />
      </Comp>
    );
  const t = String(text).trim();
  const parsed = looksJson(t) ? tryJson(t) : undefined;
  const body: ReactNode =
    parsed !== undefined ? (
      <Json value={parsed} title={title} />
    ) : looksDiff(t) ? (
      <Diff text={t} title={title} />
    ) : (
      <CodeBlock lang="" text={t} title={title} />
    );
  return <Comp el="V.output">{body}</Comp>;
}

const XML_RE = /<([A-Za-z_][\w.-]*)(\s[^>]*)?>([\s\S]*?)<\/\1>/g;
const looksMarkdown = (s: string): boolean => s.startsWith("#") || s.startsWith("- ") || s.includes("\n- ");

/** Harness-injected messages are XML-tagged sections; each top-level element becomes a titled block. */
export function Xmlish({ text }: { text: unknown }) {
  const s = String(text ?? "");
  const out: ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  const re = new RegExp(XML_RE.source, "g");
  while ((m = re.exec(s))) {
    const before = s.slice(last, m.index).trim();
    if (before) out.push(<Text key={`b${m.index}`} text={before} />);
    const inner = (m[3] ?? "").trim();
    const nested = inner.includes("<") && /<([A-Za-z_][\w.-]*)[\s>]/.test(inner);
    const body = nested ? <Xmlish text={inner} /> : looksMarkdown(inner) ? <Code lang="markdown" text={inner} /> : <Text text={inner} />;
    out.push(
      <div key={`x${m.index}`} className="block xml" style={{ borderLeftColor: categoryColour("harness_context") }}>
        <div className="bhead">
          <span className="tag">&lt;{m[1]}&gt;</span>
          {m[2] ? (
            <>
              {" "}
              <Mono>{m[2].trim()}</Mono>
            </>
          ) : null}
        </div>
        {body}
      </div>,
    );
    last = re.lastIndex;
  }
  const tail = s.slice(last).trim();
  if (tail) out.push(<Text key="tail" text={tail} />);
  return <Comp el="V.xmlish">{out.length ? out : <Text text={s} />}</Comp>;
}

/** `- name: description` listings (skills, agents) as a two-column table. */
export function Listing({ text }: { text: unknown }) {
  const rows = String(text ?? "")
    .split("\n")
    .map((l) => /^\s*-\s*([^:]+?):\s*(.*)$/.exec(l))
    .filter((r): r is RegExpExecArray => Boolean(r));
  if (!rows.length) return <Code lang="markdown" text={text} />;
  return (
    <Comp el="V.listing">
      <table className="list">
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td>
                <Mono>{r[1]!.trim()}</Mono>
              </td>
              <td>{r[2]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Comp>
  );
}

const code = (v: unknown): ReactNode => (v ? <Mono>{String(v)}</Mono> : undefined);
const str = (v: unknown): string | undefined => (v == null ? undefined : String(v));

/** The collapsible record envelope: the harness's bookkeeping fields around the payload. */
export function Envelope({ rec }: { rec: Record<string, unknown> }) {
  const payload = (rec.payload ?? {}) as Record<string, unknown>;
  const passthrough = payload.internal_chat_message_metadata_passthrough as Record<string, unknown> | undefined;
  return (
    <Comp el="V.envelope">
      <Details summary="record envelope">
        <Kvs
          pairs={[
            ["timestamp", str(rec.timestamp)],
            ["uuid", code(rec.uuid)],
            ["parentUuid", code(rec.parentUuid)],
            ["requestId", code(rec.requestId)],
            ["sessionId", code(rec.sessionId)],
            ["ordinal", str(rec.ordinal)],
            ["isSidechain", rec.isSidechain === undefined ? undefined : String(rec.isSidechain)],
            ["cwd", code(rec.cwd)],
            ["version", str(rec.version)],
            ["gitBranch", str(rec.gitBranch)],
            ["entrypoint", str(rec.entrypoint)],
            ["userType", str(rec.userType)],
            ["effort", str(rec.effort)],
            ["promptId", code(rec.promptId)],
            ["turn_id", code(payload.turn_id)],
            ["create_time", str(passthrough?.create_time)],
          ]}
        />
      </Details>
    </Comp>
  );
}
