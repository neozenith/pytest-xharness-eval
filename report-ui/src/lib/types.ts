/**
 * The shapes `report.py`, `history.py` and `runresult.py` write. Names are the JSON keys
 * (ADR 0021: a metric name carries its unit and its source); keep them in step with the
 * glossary, not with what reads nicely in TypeScript.
 */

/**
 * `rates_applied`: the price row one result was priced with (ADR 0021, ADR 0050). Every key
 * is optional because `{}` is an unpriced result. Since ADR 0050 the tier rates are USD per
 * million tokens and `unit` says so; a record without `unit` predates it and its rates are
 * USD per token. Read the tiers through `ratesPerMtok` (`lib/rates.ts`), never directly.
 */
/** `rates_applied.long_context`: a threshold on one call's prompt tokens, and the five tiers billed above it (ADR 0051). */
export interface LongContextRates {
  above_prompt_tokens: number;
  input: number;
  output: number;
  cache_read: number;
  cache_write: number;
  cache_write_1h: number;
}

export interface RatesApplied {
  input?: number;
  output?: number;
  cache_read?: number;
  cache_write?: number;
  cache_write_1h?: number;
  /** The tier a call is billed at, in full, once its prompt exceeds `above_prompt_tokens` (ADR 0051); null or absent where the row has none. */
  long_context?: LongContextRates | null;
  unit?: string;
  harness?: string;
  model?: string;
  source?: string;
  effective_from?: string | null;
  effective_to?: string | null;
  applied_at?: string;
}

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
  /** What the case declared (ADR 0044): the same string on every arm. */
  task: string | null;
  /** What this harness rendered around the task and actually sent. Differs per arm. */
  prompt: string | null;
  harness: string;
  model: string;
  /**
   * The reasoning rung this cell ran at, resolved to its harness's own ladder (ADR 0049).
   * Null when the cell named none and inherited the CLI's default — and on every session
   * captured before the axis existed, which is why it is a facet value like any other and
   * never a filter the page applies on its own.
   */
  effort: string | null;
  /**
   * The named treatment layered over the case's fixture (ADR 0055), or null for its control —
   * the untreated arm every treated case also sweeps — and on every session captured before the
   * axis existed. Unlike a null rung, a control is a measured arm: it is labelled and selectable
   * as `control` (`lib/treatment.ts`).
   */
  treatment: string | null;
  /** The model's product line from the catalogue (ADR 0057): `opus`, `sol`, …; null when it never described the model, or on a capture before it. */
  line: string | null;
  /**
   * The model's numbered role in its provider's lineup (ADR 0057), 1 the smallest: a number, never a
   * name, so it compares across providers. Null on a model the catalogue never described.
   */
  family_tier: number | null;
  /** The model's release date, `YYYY-MM-DD` (ADR 0057); null when the catalogue does not say. */
  released: string | null;
  session_id: string;
  verdict: string | null;
  at: string | null;
  node: string | null;
  wall_ms: number | null;
  result: string;
  log: string | null;
  estimated_cost_usd: number | null;
  harness_reported_cost_usd: number | null;
  rates_applied: RatesApplied;
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
  /** The Important Metrics a result carries beyond the fields above (ADR 0071); absent on an older index. */
  subagent_token_share?: number | null;
  subagent_cost_share?: number | null;
  compactions?: number | null;
  reasoning_share?: number | null;
  output_tokens_per_sec_by_model?: Record<string, number>;
  tool_calls: number;
  duration_ms: number | null;
  files_written: string[];
  has_ledger: boolean;
  record_kinds: Record<string, number>;
  skill_coverage: SkillCoverageSummary;
}

/** How a metric's samples are distributed, which fixes its aggregates (`model/metrics.py`, ADR 0071). */
export type MetricKind = "spread" | "fraction" | "rare" | "rate";

/** What a metric's value is measured in. */
export type MetricUnit = "usd" | "tokens" | "percent" | "share" | "count" | "ms" | "tokens_per_sec";

/** One Important Metric as `model/metrics.py` declares it; `aggregates` lists its keys, headline first. */
export interface ImportantMetric {
  id: string;
  label: string;
  field: string;
  per: string | null;
  kind: MetricKind;
  unit: MetricUnit;
  why: string;
  aggregates: string[];
}

/** One aggregate name -> its value over a cell's samples; every value but `n` is null with no samples. */
export type Aggregates = Record<string, number | null>;

/** One cell's samples reduced (`emit/samples.py`): its identity, sample count, and each metric's aggregates by id. */
export interface CellSamples {
  skill: string | null;
  case: string;
  harness: string;
  model: string;
  effort: string | null;
  treatment: string | null;
  samples: number;
  metrics: Record<string, Aggregates>;
}

/** `index.json`'s `important_metrics`: the declared set and every cell's aggregates over it (ADR 0071). */
export interface ImportantMetricsDoc {
  metrics: ImportantMetric[];
  cells: CellSamples[];
}

export interface Index {
  generated_at: string;
  captured: string;
  inline: boolean;
  cells: Cell[];
  /** Absent on an index written before ADR 0071; `fromWire` folds that to an empty document. */
  important_metrics?: ImportantMetricsDoc;
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
  /** When the log recorded the call and its result (ADR 0073); empty when it has no such record, absent before. */
  started_at?: string;
  ended_at?: string;
  duration_ms?: number | null;
}

/** One later call's share of carrying a tool's result (ADR 0073). */
export interface ToolCharge {
  turn: number;
  /** Re-read from the prompt cache, rather than read fresh. */
  cached: boolean;
  usd: number;
}

/** One tool call of any thread: timed, and priced as issued and as carried in context (ADR 0073). */
export interface ToolCost {
  /** Empty for the primary, else the subagent's id. */
  thread: string;
  /** That thread's turn that issued it. */
  turn: number;
  id: string;
  name: string;
  summary: string;
  started_at: string;
  ended_at: string;
  duration_ms: number | null;
  issuing_cost_usd: number;
  result_tokens: number;
  context_cost_usd: number;
  cache_rereads: number;
  trace: ToolCharge[];
}

/** One touch of one skill file, with the figures of the tool call that made it (ADR 0073). */
export interface SkillEvent {
  thread: string;
  /** The primary turn it is credited to. */
  turn: number;
  tool_id: string;
  tool: string;
  path: string;
  access: "loaded" | "run";
  started_at: string;
  duration_ms: number | null;
  issuing_cost_usd: number | null;
  context_cost_usd: number | null;
}

/** When the skill under test was triggered, how long it was in use, and its tool calls' cost (ADR 0073). */
export interface SkillUse {
  skill: string;
  /** `prompt` when the run's invocation named it, else the first tool that touched it. */
  trigger: string;
  triggered_turn: number;
  triggered_at: string;
  last_turn: number;
  last_at: string;
  duration_ms: number | null;
  tool_calls: number;
  issuing_cost_usd: number;
  context_cost_usd: number;
  cache_rereads: number;
  events: SkillEvent[];
}

/**
 * One shell command the harness itself reported as executed, after its own expansion
 * (Codex's `CommandExecution`). Empty for a harness that logs no such record (ADR 0048).
 */
export interface ExecutedCommand {
  tool: string;
  command: string;
  cwd: string;
}

/** A tool result that entered a call's context: the previous turn's output of that tool. */
export interface ResultIn {
  tool: string;
  chars: number;
  content: string;
  /** The tool call it answers (ADR 0073); absent on a result written before it. */
  id?: string;
}

/** One model call of the per-call ledger (ADR 0019, ADR 0023). */
export interface Call {
  n: number;
  at: string;
  usage: Usage;
  tools: ToolCall[];
  /** Absent in a `result.json` captured before ADR 0048. */
  executed?: ExecutedCommand[];
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
 * One thread the session spawned, at any depth, with its own captured transcript and ledger,
 * linked to the record that spawned it (ADR 0072). `parent_turn` is the primary turn it
 * descends from; its usage is already folded into the run's `usage` (the whole bill), never
 * double-counted here. The link and span fields are absent on a result written before ADR 0072.
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
  model?: string;
  estimated_cost_usd?: number | null;
  /** The spawn record's id: Claude's `tool_use.id`, Codex's `call_id` or `CollabAgentToolCall` item id. */
  spawned_by?: string;
  /** The spawning thread's id, empty for the primary. */
  parent?: string;
  /** 1 for a thread the primary spawned, one more per subagent in between. */
  depth?: number;
  started_at?: string;
  ended_at?: string;
  duration_ms?: number | null;
  output_tokens_per_sec?: number | null;
}

/** A `.result.json`; only the fields the page reads are typed. */
export interface RunResult {
  harness: string;
  model: string;
  effort: string | null;
  /** The treatment (ADR 0055); null for a control, absent on a result written before the axis. */
  treatment?: string | null;
  /** The catalogue's facts about the model (ADR 0057); null when undescribed, absent on a result written before it. */
  line?: string | null;
  family_tier?: number | null;
  released?: string | null;
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
  rates_applied: RatesApplied;
  /** How many calls were billed at the long-context tier; null while unpriced, absent on results before ADR 0051. */
  long_context_calls?: number | null;
  final_text: string;
  files_written: string[];
  tool_calls: Record<string, number>;
  record_kinds: Record<string, number>;
  /** Compactions of the primary thread's context (ADR 0071); absent on a result written before it. */
  compactions?: number;
  reasoning_share?: number | null;
  subagent_token_share?: number | null;
  subagent_cost_share?: number | null;
  /** Output tokens per second of call latency, per model that answered (ADR 0071). */
  output_tokens_per_sec_by_model?: Record<string, number>;
  skill_coverage: Record<string, unknown>;
  /** Every tool call of every thread, timed and priced (ADR 0073); absent on a result written before it. */
  tool_costs?: ToolCost[];
  /** The skill under test's span and cost; `{}` when nothing triggered it, absent before ADR 0073. */
  skill_use?: SkillUse | Record<string, never>;
  case: { suite?: string; name?: string; skill?: string; fixture?: string; task?: string; prompt?: string };
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
