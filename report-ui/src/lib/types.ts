/**
 * The shapes `report.py`, `history.py` and `runresult.py` write. Names are the JSON keys
 * (ADR 0021: a metric name carries its unit and its source); keep them in step with the
 * glossary, not with what reads nicely in TypeScript.
 */

export interface SkillCoverageSummary {
  files?: number;
  ignored?: number;
  docs?: number;
  scripts?: number;
  tests?: number;
  assets?: number;
  loaded?: number;
  run?: number;
}

/** One row of `index.json` `cells`: one captured session. */
export interface Cell {
  case: string;
  suite: string | null;
  skill: string | null;
  fixture: string | null;
  prompt: string | null;
  harness: string;
  model: string;
  session_id: string;
  verdict: string | null;
  at: string | null;
  node: string | null;
  wall_ms: number | null;
  result: string;
  log: string | null;
  estimated_cost_usd: number | null;
  harness_reported_cost_usd: number | null;
  rates_applied: Record<string, unknown>;
  accumulative_billed_tokens: number | null;
  baseline_tokens: number | null;
  context_window: number | null;
  peak_context_tokens: number | null;
  context_window_pct: number | null;
  final_context_pct: number | null;
  ttft_ms: number | null;
  output_tokens_per_sec: number | null;
  turns: number | null;
  reported_turns: number | null;
  subagents?: number;
  tool_calls: number;
  duration_ms: number | null;
  files_written: string[];
  has_ledger: boolean;
  record_kinds: Record<string, number>;
  skill_coverage: SkillCoverageSummary;
}

export interface Index {
  generated_at: string;
  captured: string;
  inline: boolean;
  cells: Cell[];
}

export interface Usage {
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  cache_write_1h_tokens: number;
  cache_write_5m_tokens: number;
  reasoning_tokens: number;
  accumulative_billed_tokens?: number;
}

export interface ToolCall {
  name: string;
  input: unknown;
  summary?: string;
  /** The harness's tool-use id (Claude `tool_use.id`, Codex `call_id`); a subagent points back at it. */
  id?: string;
}

/** A tool result that entered a call's context: the previous turn's output of that tool. */
export interface ResultIn {
  tool: string;
  chars: number;
  content: string;
}

/** One model call of the per-call ledger (ADR 0019, ADR 0023). */
export interface Call {
  n: number;
  at: string;
  usage: Usage;
  tools: ToolCall[];
  text: string;
  thinking: string;
  stop_reason: string | null;
  latency_ms: number | null;
  context_tokens: number;
  context_pct: number | null;
  output_tokens_per_sec: number | null;
  records: number[];
  results_in: ResultIn[];
}

/**
 * One parallel thread the session spawned, with its own captured transcript and ledger.
 * `parent_turn` is the primary turn whose tool call spawned it; its usage is already
 * folded into the run's `usage` (the whole bill), never double-counted here.
 */
export interface Subagent {
  agent: string;
  id: string;
  log: string;
  parent_turn: number | null;
  turns: number;
  description: string;
  usage: Usage;
  calls: Call[];
}

/** A `.result.json`; only the fields the page reads are typed. */
export interface RunResult {
  harness: string;
  model: string;
  session_id: string;
  turns: number;
  reported_turns: number | null;
  usage: Usage;
  calls: Call[];
  context_window: number | null;
  peak_context_tokens: number;
  final_context_tokens: number;
  context_window_pct: number | null;
  final_context_pct: number | null;
  baseline_tokens: number;
  estimated_cost_usd: number | null;
  harness_reported_cost_usd: number | null;
  rates_applied: Record<string, unknown>;
  final_text: string;
  files_written: string[];
  tool_calls: Record<string, number>;
  record_kinds: Record<string, number>;
  skill_coverage: Record<string, unknown>;
  case: { suite?: string; name?: string; skill?: string; fixture?: string; prompt?: string };
  subagents?: Subagent[];
  [key: string]: unknown;
}

export interface ThemeTokens {
  bg: string;
  panel: string;
  ink: string;
  muted: string;
  line: string;
  accent: string;
  good: string;
  bad: string;
  warn: string;
  code: string;
  grid: string;
  /** The chart's baseline, spine and ticks: a step past `grid`, so the anchor outranks the ladder. */
  axis: string;
  plot: string;
  series: string[];
  waterfall: Record<string, string>;
  hljs?: string;
}

/** `report.tokens.json` (ADR 0024). */
export interface DesignTokens {
  $schema?: string;
  name?: string;
  fonts?: { body?: string; mono?: string };
  themes: { light: ThemeTokens; dark: ThemeTokens };
  categories: Record<string, string>;
}

/** What `report.py` embeds as `window.__XH_DATA__` for an inline page. */
export interface InlineData {
  index: Index;
  results: Record<string, RunResult>;
  logs: Record<string, string>;
  tokens: DesignTokens;
}

declare global {
  interface Window {
    __XH_DATA__?: InlineData;
    /** Count of in-flight data loads; `0` means every started fetch has settled (see `lib/data.ts`). */
    __XH_PENDING__?: number;
  }
}
