# Autonomous Agent — Design, Usage, and Validation Results

## What this actually is (read this first)

The "autonomous" agent is currently **a prompt (`docs/agent_prompt.txt`) run in a fresh Claude Desktop chat**, with a human present to accept Claude Desktop's tool-use confirmations and manually click "continue" if a response hits Claude Desktop's length limit mid-loop. It is **not** an unattended background process — there is no scheduler, no headless script, no API integration running it independently. This was a deliberate choice (see "Why not the API" below), not an oversight. If you need genuinely unattended operation, that's a real next step, not something this setup already does.

## Setup

1. Follow `docs/custom-tools.md` to get the MCP server running with all 9 tools connected in Claude Desktop.
2. Confirm `prices` is populated for whatever ticker/date range your goal needs (`docs/gotchas.md` #7 — this table doesn't persist across restarts).
3. Confirm `strategy.q`/`history.q` are loaded in your current q session (`docs/gotchas.md` #1 — also doesn't persist).
4. Open a **fresh** Claude Desktop chat (not a continuation of another conversation — leftover context can bias its parameter choices or session-id handling).
5. Paste the full contents of `docs/agent_prompt.txt`, editing only the final `GOAL:` line to your actual target (ticker, strategy, metric, hard constraint, iteration cap).
6. Let it run, accepting tool-use confirmations and clicking "continue" if needed.

## Why not the Anthropic API

A real production version of this would likely be a standalone script calling the Messages API directly in a `while` loop — full control, no UI-imposed length limits, genuinely unattended. That was deliberately not built for this project; the prompt-in-Claude-Desktop approach was chosen instead, accepting the manual-continuation limitation as a tradeoff.

## Validated behavior (5 full test runs)

| Test | Strategy/Window | Result |
|---|---|---|
| 1 | ma_crossover, AAPL, Jan–Jun 2024, DD<25% | Found best config (20/50) via non-monotonic search; correct final report |
| 2 | Same, with an explicit numeric stopping-counter fix | Confirmed fixed: stopped exactly at 2 non-improving rounds, no longer ran an extra "confirming" round |
| 3 | Same, but DD<2% (deliberately unachievable) | Correctly found **zero** valid runs; explicitly refused to name a "best" run despite one run having a good Sharpe; correctly diagnosed *why* (strategy has no independent risk control) |
| 4 | ma_crossover, AAPL, 2020–2024 (real trade logs, real ~30% drawdown regime) | Correctly navigated real trade_log data; found a genuine Pareto-improving config (5/15) satisfying the constraint |
| 5 | rsi, AAPL, 2020–2024 | Correctly found **zero** valid runs; diagnosed that drawdown was driven by *which* market shock was held through, not by RSI threshold tightness (two very different threshold sets produced *identical* drawdown) — correctly recommended a structural fix (risk-control layer) over further parameter tuning |

A 6th real-world run additionally surfaced and correctly diagnosed a genuine infrastructure failure (`strategy.q` functions not reloaded after a restart — see `docs/gotchas.md` #1): the agent systematically varied strategy/params/date-range/session-id, ruled each out as the cause, correctly identified a persistent backend fault, and stopped with a clear report rather than hallucinating a result or retrying forever.

## Known issue found and fixed during testing

**Original bug**: the stopping rule ("no improvement for 2 consecutive rounds") was tracked in prose narration, with no explicit counter. This led to self-contradictory reasoning in one run ("we haven't hit 2 consecutive non-improving rounds yet... that's already 2 non-improving rounds") and an extra, unnecessary iteration.

**Fix**: `docs/agent_prompt.txt` now requires explicit numeric state after every run — `current_best_sharpe = X` and `consecutive_non_improving_rounds = N`, updated by a deterministic rule, not narrated. Confirmed fixed in Test 2 above.

## Known remaining gaps

- **Floating-point precision inconsistency**: observed printing `current_best_sharpe` with 3 vs. 4 decimal places across different runs. Harmless so far (no two results have been close enough for this to change a decision), but worth fixing with an explicit rounding rule if you ever see two runs with very close Sharpe values.
- **No test yet of a strategy that closes a real winning AND losing trade within the same session** under a binding constraint — Test 4 came closest (16-51 real trades across runs) but a more targeted test isolating win/loss trade attribution under constraint pressure hasn't been run.
- **No genuinely unattended run** — every test here had a human present. Real step-6-style "end to end" automation (per the original build order) would need the API-script approach that was explicitly deferred (see "Why not the API" above).
