# Token accounting: how `total_tokens` and `peak_context_tokens` are calculated

A reference for the two token figures on every report row, worked slowly from what
the providers report, with each step justified against their documentation and
cross-checked against the numbers the harnesses themselves produce. Written after a
row read as "1,504,090 tokens consumed of a 1M window, 12%", which looks like a
contradiction and is not.

Sources were fetched on 2026-08-23; quotations are verbatim. The billed sum was called
`total_tokens` until ADR 0029 renamed it `accumulative_billed_tokens` the same day; the
vendors' own `total_tokens` fields keep their names and are quoted as such below.

- Anthropic, *Context windows*: <https://platform.claude.com/docs/en/build-with-claude/context-windows>
- Anthropic, *Prompt caching*: <https://platform.claude.com/docs/en/docs/build-with-claude/prompt-caching>
- Claude Code, *Status line* (`context_window` fields): <https://code.claude.com/docs/en/statusline>
- OpenAI, *Prompt caching*: <https://developers.openai.com/api/docs/guides/prompt-caching>

## The one-paragraph answer

`peak_context_tokens` is the **largest single prompt** any one model call processed:
for that call, `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`.
It is what "context window usage" means to both providers and to Claude Code's own
status line. `context_window_pct` is that number over the model's window.

`total_tokens` is the **sum of every billed token over every call** of the run. An
agent re-sends the whole conversation on every call, so the same prefix is processed
and billed again on each turn (at the cache-read rate when it was cached). Over 16
turns of a ~100k-token conversation that sum is necessarily around a million even
though the window never got past 12% full. The two numbers measure different things:
one is a *size*, the other is *spend*. Showing them in adjacent columns with no unit
was the report's mistake, now fixed.

## 1. Vocabulary

| Term | Meaning here |
|------|--------------|
| **call** / **turn** | one request to the model API and its response. The plugin's `turns` counts these (Claude: distinct `message.id`; Codex: `token_count` events). The CLI's own "turn" (a user message and everything until the agent stops) is `reported_turns`. |
| **prompt** of a call | everything sent in that request: system prompt, tool definitions, every earlier message including tool results, and the new message. |
| **context window** | the maximum tokens a single call may hold: its prompt plus what it generates. Reported by the harness per model (Claude: `modelUsage[<model>].contextWindow`; Codex: `model_context_window`). |
| **billed tokens** | what the provider charges for, in tiers with different prices. |

## 2. What the providers report per call

### Anthropic (Claude Code runs on the Messages API)

Every response carries a `usage` object. From *Prompt caching*:

> - `cache_creation_input_tokens`: Number of tokens written to the cache when creating a new entry.
> - `cache_read_input_tokens`: Number of tokens retrieved from the cache for this request.
> - `input_tokens`: Number of input tokens which were not read from or used to create a cache (that is, tokens after the last cache breakpoint).

and the formula the page gives:

> `total_input_tokens = cache_read_input_tokens + cache_creation_input_tokens + input_tokens`

with its worked example: 100,000 cached + 0 written + 50 new = **100,050 tokens processed**.

So on Anthropic the three input fields are **disjoint**; `input_tokens` is *only* the
uncached tail. That is the single most important fact in this document, because it is
the opposite of OpenAI's convention.

From *Context windows*, on what counts toward the window:

> Everything in the request counts toward the context window: the system prompt, every message in `messages` (including tool results, images, and documents), and your tool definitions. The output Claude generates for the turn, including its extended thinking, counts too. Every response reports what the request consumed in its `usage` field. If you use prompt caching, the input count is split across `input_tokens`, `cache_read_input_tokens`, and `cache_creation_input_tokens`, and all three count toward the window.

and, to kill the intuition that cached tokens are "free" in the window:

> Cached prompt prefixes still occupy the context window: prompt caching changes what you pay for those tokens, not whether they count.

On thinking:

> Thinking tokens are a subset of your `max_tokens` parameter, are billed as output tokens, and count toward rate limits.

So `output_tokens` already contains thinking; `output_tokens_details.thinking_tokens`
is a breakdown, not an extra.

Prices, from *Prompt caching*: 5-minute cache writes 1.25× base input, 1-hour cache
writes 2× base input, cache reads 0.1× base input.

### Claude Code itself

Claude Code's status line exposes the same arithmetic, from *Status line*:

> `context_window.total_input_tokens` is the sum of `input_tokens`, `cache_creation_input_tokens`, and `cache_read_input_tokens`; `total_output_tokens` is the output tokens from the most recent response.

and:

> The `used_percentage` field is calculated from input tokens only: `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`. It does not include `output_tokens`.

That is: the percentage Claude Code shows its user is **the latest call's prompt size
over the window**. It is not a running sum of anything.

### OpenAI (Codex runs on the Responses API)

From *Prompt caching* (GPT-5.6+ usage shape):

```json
{ "usage": { "input_tokens": 2600, "input_tokens_details": { "cached_tokens": 2000, "cache_write_tokens": 400 } } }
```

> In this example, 2,000 tokens were read from the cache and 400 additional tokens were written. The remaining 200 input tokens were neither read nor written.

So on OpenAI `input_tokens` is the **whole prompt**, and cached / written tokens are
**subsets** of it. Codex's rollout log flattens this into `last_token_usage`
`{input_tokens, cached_input_tokens, cache_write_input_tokens, output_tokens, reasoning_output_tokens, total_tokens}`, and its `total_tokens` is `input_tokens + output_tokens` (checked below), which shows `reasoning_output_tokens` is inside `output_tokens` just as Anthropic's thinking is.

Cached input is billed at 0.1× the uncached rate.

## 3. The plugin's per-call record

`normalise.py` maps each harness into one `Usage` per call with **Anthropic's disjoint
shape**, because that is the shape in which each tier prices once:

| `Usage` field | Claude source | Codex source |
|---------------|---------------|--------------|
| `input_tokens` | `input_tokens` (already disjoint) | `input_tokens − cached_input_tokens − cache_write_input_tokens` |
| `cache_read_tokens` | `cache_read_input_tokens` | `cached_input_tokens` |
| `cache_write_tokens` | `cache_creation_input_tokens` (split 1h / 5m from `cache_creation`) | `cache_write_input_tokens` |
| `output_tokens` | `output_tokens` | `output_tokens` |
| `reasoning_tokens` | `output_tokens_details.thinking_tokens` (a breakdown of output, not added) | `reasoning_output_tokens` (likewise) |

The Codex subtraction is what makes the two dialects comparable. Before 2026-08-23 it
subtracted only `cached_input_tokens`; `cache_write_input_tokens` was added as a
separate tier without being removed from `input_tokens`, which would have double-counted
writes. Every captured Codex call so far reports `cache_write_input_tokens: 0`, so no
stored number was affected, but the arithmetic was wrong and is now fixed (with a test).

## 4. `context_tokens` of a call, and `peak_context_tokens`

```text
context_tokens(call) = input_tokens + cache_read_tokens + cache_write_tokens
```

This is exactly Anthropic's `total_input_tokens` and Claude Code's `used_percentage`
numerator, and on Codex it reconstructs OpenAI's raw `input_tokens` (the subtraction
in §3 undone). It is the prompt that call processed: the conversation as it stood when
the call was made. It is **measured by the provider**, not estimated by counting
characters, so whatever the server kept or dropped of earlier thinking is already
inside it.

```text
peak_context_tokens   = max over calls of context_tokens(call)
context_window_pct    = 100 × peak_context_tokens / context_window
final_context_tokens  = context_tokens(last call) + output_tokens(last call)
final_context_pct     = 100 × final_context_tokens / context_window
baseline_tokens       = context_tokens(first call)
```

Why the peak: the question the percentage answers is "how close did this run come to
the limit", and the limit applies per call. The run's worst moment is its largest
prompt.

Why `final_context_tokens` adds the last output: Anthropic's definition of the window
includes "the output Claude generates for the turn". Claude Code's status line
deliberately leaves output out ("calculated from input tokens only"). The plugin's
per-call `context_pct` matches Claude Code; `final_context_pct` is the only figure that
adds output, and the glossary says so. On the session below the difference is
12.02% vs 12.06%.

## 5. `total_tokens` of a run

```text
total_tokens = Σ over calls ( input_tokens + output_tokens + cache_read_tokens + cache_write_tokens )
```

Every tier that carries a price, summed over every call. `reasoning_tokens` is not
added because it is already inside `output_tokens` (§2).

Why the cached prefix is counted again on every call: because it is **sent and
processed again on every call**. The API is stateless; an agent loop re-sends the
entire conversation each time. Caching changes the price of that prefix from 1× to
0.1×, not whether it is processed or billed, and both providers report it as usage on
every call. A sum of usage that skipped cache reads would not reconcile with the bill.

This is the same definition both harnesses use for their own totals:

- Claude Code's envelope `usage` is the sum of every call's `usage`, tier by tier. For
  the session below the plugin's ledger sum and the envelope are identical in every
  field: 32 / 37,009 / 1,371,238 / 95,811.
- Codex's `total_token_usage.total_tokens` is its own running sum. For the Codex
  session below it is 527,801, and the plugin's `total_tokens` is 527,801.

**Subagents (ADR 0033).** A session that spawns parallel threads (Claude's Agent
tool, Codex's thread forks) produces one transcript per thread, and every one of
those threads' calls is billed by the provider exactly like the primary's. The
plugin folds each subagent's per-call sum into the run's `usage`, so the run's
`accumulative_billed_tokens` and `estimated_cost_usd` are the whole bill; each
thread's own ledger lives on `result.subagents[*].calls`, attributed to the
primary turn that spawned it (`parent_turn`). The harness aggregates do **not**
fold: measured on the discovery sweep (2026-08-28), Claude's envelope `usage`
equals the primary ledger's sum exactly and Codex's `total_token_usage` is the
primary rollout's own sum, so on a spawning run the reconciliation delta
between the run's `usage` and the harness's figure is the subagents' bill, not
a ledger error, and the report says so beside the comparison.

## 6. Worked example: `eval_dual_density`, `claude-sonnet-5`, session `1feb573f…`

From `claude-1feb573f-….result.json`; the harness reported `contextWindow: 1000000`.
All 16 calls, in order:

| call | input | cache_read | cache_write (1h) | output | of which thinking | **context_tokens** | % of 1M |
|-----:|------:|-----------:|-----------------:|-------:|------------------:|-------------------:|--------:|
| 1 | 2 | 24,432 | 11,165 | 185 | 25 | **35,599** | 3.56 |
| 2 | 2 | 35,597 | 268 | 308 | 52 | 35,867 | 3.59 |
| 3 | 2 | 35,865 | 4,234 | 264 | 42 | 40,101 | 4.01 |
| 4 | 2 | 40,099 | 11,231 | 466 | 178 | 51,332 | 5.13 |
| 5 | 2 | 51,330 | 15,981 | 2,347 | 2,250 | 67,313 | 6.73 |
| 6 | 2 | 67,311 | 13,444 | 27,886 | 23,783 | 80,757 | 8.08 |
| 7 | 2 | 80,755 | 28,018 | 422 | 0 | 108,775 | 10.88 |
| 8 | 2 | 108,773 | 3,529 | 645 | 453 | 112,304 | 11.23 |
| 9 | 2 | 112,302 | 1,028 | 853 | 701 | 113,332 | 11.33 |
| 10 | 2 | 113,330 | 1,081 | 526 | 0 | 114,413 | 11.44 |
| 11 | 2 | 114,411 | 844 | 207 | 0 | 115,257 | 11.53 |
| 12 | 2 | 115,255 | 322 | 499 | 148 | 115,579 | 11.56 |
| 13 | 2 | 115,577 | 1,961 | 1,242 | 1,087 | 117,540 | 11.75 |
| 14 | 2 | 117,538 | 1,412 | 445 | 0 | 118,952 | 11.90 |
| 15 | 2 | 118,950 | 763 | 328 | 0 | 119,715 | 11.97 |
| 16 | 2 | 119,713 | 530 | 386 | 0 | **120,245** | **12.02** |
| **Σ** | **32** | **1,371,238** | **95,811** | **37,009** | 28,719 | | |

Read down the table slowly; three things are visible in the raw numbers.

**Each call's `cache_read` is the previous call's `context_tokens` minus 2.** Call 2
reads 35,597 from cache; call 1's prompt was 35,599. The whole previous prompt became
cached prefix, and the 2 uncached tokens of each call (the tail after the last cache
breakpoint) join the cache on the next call. This is the mechanism that makes
`total_tokens` large: the same ~100k-token conversation is read back 15 times.

**`context_tokens` is a size that grows slowly.** It moves from 35,599 to 120,245
over 16 calls because each call adds only the model's previous message and the tool
result that answered it. Its maximum is 120,245, and 120,245 / 1,000,000 =
**12.02%**. That is the peak-context figure.

**The ratchet is exactly `cache_write`.** Since `input` is a constant 2 and
`cache_read(n) = context_tokens(n−1) − 2`:

```text
context_tokens(n) = 2 + (context_tokens(n−1) − 2) + cache_write(n)
                  = context_tokens(n−1) + cache_write(n)
```

and `cache_write(n)` is the material that did not exist when call n−1 was sent: the
model's whole output on call n−1 (text, tool call **and thinking**) plus the tool
result, plus a few framing tokens. Subtracting `output(n−1)` from `cache_write(n)`
isolates the tool result:

| call n | `cache_write(n)` | `output(n−1)` | of which thinking | remainder = tool result + framing |
|------:|-----------------:|--------------:|------------------:|----------------------------------:|
| 2 | 268 | 185 | 25 | 83 |
| 3 | 4,234 | 308 | 52 | 3,926 |
| 4 | 11,231 | 264 | 42 | 10,967 |
| 5 | 15,981 | 466 | 178 | 15,515 |
| 6 | 13,444 | 2,347 | 2,250 | 11,097 |
| **7** | **28,018** | **27,886** | **23,783** | **132** |
| 8 | 3,529 | 422 | 0 | 3,107 |
| 9 | 1,028 | 645 | 453 | 383 |

Call 7 is the proof that **thinking is carried into context on this model**: call 6
produced 23,783 thinking tokens, and call 7's prompt grew by 28,018, of which only
132 is the tool result. This is what Anthropic's *Context windows* says for Sonnet
4.6 and later: previous thinking blocks are kept by default "and they count toward the
context window like any other input tokens" (and inside a tool-use cycle the thinking
block *must* be returned with the tool result). On Haiku and pre-4.6 models the API
strips them and the same row would show a remainder near the tool-result size alone.

So the answer to "what increments `context_tokens`" is: everything the model wrote
last call, thinking included, plus what the tools returned. `output(n)` is not in
`context_tokens(n)` because it did not exist when that prompt was sent; it appears one
call later as `cache_write(n+1)`. `final_context_tokens` adds the last output for
exactly that reason: there is no call n+1 to carry it.

**What a thinking token costs over the run.** Because it is carried forward, a token
of thinking is billed three ways: as output when generated, as a cache write on the
next call, and as a cache read on every call after that. Call 6's 23,783 thinking
tokens, at the rates below:

```text
output       23,783 × 1.0e-5          = 0.2378
cache write  23,783 × 4.0e-6          = 0.0951   (call 7, 1h TTL)
cache reads  23,783 × 2.0e-7 × 9      = 0.0428   (calls 8–16)
                                        ------
                                        0.3757   ≈ 37% of the session's $1.03
```

**Why `input` is 2 on every call.** Anthropic defines `input_tokens` as the tokens
after the last cache breakpoint. Claude Code places its last breakpoint on the final
block of the final message, so the only tokens after it are the framing that opens the
assistant turn: 2 on this model, on all 16 calls. (This reading follows from the field
definition and the data; Claude Code does not document the figure.) Codex's uncached
tail is larger and varies (2,420 on its last call) because OpenAI caches prefixes at a
block granularity: every `cached_input_tokens` value in the captured rollouts is a
multiple of 128 (41,728; 42,752; 44,800; 27,392; 28,416), so the tail is the new
material plus the partial block before it.

**`total_tokens` is a sum that grows fast.**

```text
total_tokens = 32 + 37,009 + 1,371,238 + 95,811 = 1,504,090
```

1,371,238 of it, 91%, is cache reads: the conversation re-sent on every call. Divide
1,504,090 by the mean prompt size (91,693) and you get 16.4, about the number of calls. That
is the whole relationship between the two figures: `total_tokens ≈ turns × typical
context_tokens`. It is not a coincidence that a 16-turn run at ~12% of a 1M window
bills about 1.5M tokens; it is arithmetic.

**Final context.** Call 16 processed 120,245 and generated 386, so
`final_context_tokens = 120,631` and `final_context_pct = 12.06%`.

### The cost, as a cross-check of the tiers

`rates_applied` for the run (the project's `claude-sonnet-5` override row; since ADR 0030 an `xharness_prices` ini line): input $2/M,
output $10/M, cache read $0.20/M, cache write (1h) $4/M.

```text
       32 × 2.0e-6  =  0.0000640
   37,009 × 1.0e-5  =  0.3700900
1,371,238 × 2.0e-7  =  0.2742476
   95,811 × 4.0e-6  =  0.3832440
                      ---------
                      1.0276456
```

Claude Code's own `modelUsage["claude-sonnet-5"].costUSD` for this session is
**1.0276456**: identical to seven significant figures, which means the plugin's tiers,
its sum, and its prices all agree with the harness. The envelope's
`total_cost_usd` is 1.0287836; the difference, 0.001138, is exactly the
`costUSD` of the `claude-haiku-4-5` side call Claude Code makes to title the session
(`inputTokens: 1063, outputTokens: 15`). The report's `harness_reported_cost_usd`
carries that larger figure on purpose, and the glossary notes the side call.

### The Codex counterpart

`eval_dual_density`, `gpt-5.6-terra`, session `01a02d7f-c337…`, window 258,400, 14 calls.

Last call as Codex wrote it: `input_tokens: 47,220, cached_input_tokens: 44,800, cache_write_input_tokens: 0, output_tokens: 531, reasoning_output_tokens: 380`.
After §3's split: `input 2,420 + cache_read 44,800 + cache_write 0 = context_tokens 47,220`, OpenAI's raw prompt size recovered.
`peak_context_tokens = 47,220`, 47,220 / 258,400 = **18.27%**.

Codex's own cumulative `total_token_usage`: `input_tokens: 517,418, cached_input_tokens: 471,552, output_tokens: 10,383, total_tokens: 527,801`. 517,418 + 10,383 = 527,801, so Codex's total is input plus output with reasoning inside output, and the plugin's `total_tokens` for the run is 527,801, the same number by a different route (45,866 + 471,552 + 0 + 10,383).

## 7. Why "1.5M of a 1M window" is a category error

The row showed `total_tokens` = 1,504,090 next to `context %` = 12.0% / 1M. Neither
number is wrong. Pairing them implies 1,504,090 is a quantity that could be compared
with 1,000,000, and it is not: it is a sum over 16 separate requests, none of which
was larger than 120,245. The correct pairing for the window is `peak_context_tokens`,
and the report now shows `120,245 · 12.0% of 1M` in one cell and
`total_tokens (billed)` in another.

An analogy: a bus with 50 seats that runs 16 trips carries 800 passenger-trips. "800
of 50 seats" is not a meaningful sentence; "peak load 48 of 50 seats, 800
passenger-trips billed" is.

## 8. Fact-check ledger

Every claim the report depends on, where it was checked, and what was found.

| Claim | Checked against | Result |
|-------|-----------------|--------|
| Anthropic `input_tokens` excludes cache reads and writes | *Prompt caching*, field definitions and the `total_input_tokens` formula | **Confirmed**, verbatim above |
| All three Anthropic input tiers count toward the context window | *Context windows* | **Confirmed**, verbatim above |
| Cached tokens still occupy the window | *Context windows* | **Confirmed**, verbatim above |
| Thinking is billed as output and is a subset of it | *Context windows* | **Confirmed**, verbatim above |
| Claude Code's context percentage is the latest call's three input tiers over the window | *Status line* | **Confirmed**, verbatim above; the plugin's per-call `context_pct` is the same formula |
| Claude Code's percentage excludes output | *Status line* | **Confirmed**; the plugin's `final_context_pct` deliberately includes it (§4) |
| Cache-read, cache-write prices | *Prompt caching* | **Confirmed**: 0.1×, 1.25× (5m), 2× (1h) of input; `prices.toml` rows follow them |
| OpenAI `input_tokens` includes cached and written tokens | OpenAI *Prompt caching* example | **Confirmed**; the plugin subtracts both |
| Codex subtracted `cache_write_input_tokens` from input | `normalise._codex_call_usage` | **Was wrong**: only cached was subtracted. Fixed 2026-08-23 with a unit test. No captured value was non-zero, so no stored result changed |
| The ledger sum equals the harness's own total | Claude envelope `usage`; Codex `total_token_usage` | **Confirmed** on both harnesses, every field |
| The cost estimate equals the harness's own cost | Claude `modelUsage[...].costUSD` | **Confirmed** to 7 significant figures; the $0.001138 difference to `total_cost_usd` is the Haiku title call |
| `context_tokens` is measured, not estimated | per-call `usage` is the provider's count | **Confirmed** by construction; there is no client-side tokenisation anywhere in the plugin |

## 9. Field name map

| Plugin (`RunResult` / history / index) | Anthropic Messages API | Claude Code envelope | OpenAI Responses API / Codex rollout |
|----------------------------------------|------------------------|----------------------|--------------------------------------|
| `usage.input_tokens` | `usage.input_tokens` | `usage.input_tokens` | `input_tokens − cached − written` |
| `usage.cache_read_tokens` | `usage.cache_read_input_tokens` | `usage.cache_read_input_tokens` | `input_tokens_details.cached_tokens` / `cached_input_tokens` |
| `usage.cache_write_tokens` (+ `_1h`, `_5m`) | `usage.cache_creation_input_tokens` (+ `cache_creation.ephemeral_*`) | same | `input_tokens_details.cache_write_tokens` / `cache_write_input_tokens` |
| `usage.output_tokens` | `usage.output_tokens` | same | `output_tokens` |
| `usage.reasoning_tokens` | `usage.output_tokens_details.thinking_tokens` | same | `reasoning_output_tokens` |
| per-call `context_tokens` | `input + cache_read + cache_creation` | `context_window.total_input_tokens` | `input_tokens` (raw) |
| `context_window` | model property | `modelUsage[<model>].contextWindow` | `model_context_window` |
| `context_window_pct` | — | `context_window.used_percentage` (latest call; plugin takes the max) | — |
| per-call ratchet `context_tokens(n) − context_tokens(n−1)` | `cache_creation_input_tokens(n)` when the whole prior prompt was cached | — | `input_tokens(n) − input_tokens(n−1)` |
| `total_tokens` | — | Σ `usage` over calls | `total_token_usage.total_tokens` |

## 10. What to read on the report

- **`peak context`** (`peak_context_tokens · context_window_pct of window`): how full the
  window got. Compare with 100%.
- **`total_tokens (billed)`**: how much was processed across the run. Compare with cost,
  never with the window.
- **`baseline_tokens`**: the harness's own prompt before the agent acted; what a skill
  has to live alongside.
- **`ContextWindowChart`**: `context_pct` per call, the same numbers as the table above.
- **`TokenWaterfallChart`**: `total_tokens` decomposed by tier and by call; the tall
  grey "cache read" bars are the conversation being re-sent.
