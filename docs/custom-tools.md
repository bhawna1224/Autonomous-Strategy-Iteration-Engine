# Custom Tools — Autonomous Strategy Iteration Engine

This fork adds 6 tools to KX's stock `kdb-x-mcp-server`, supporting an LLM agent that autonomously designs, backtests, and iterates on quantitative trading strategies. The original tools (`kdbx_run_sql_query`, `kdbx_similarity_search`, `kdbx_hybrid_search`) are untouched.

## Tools added

| Tool | Purpose |
|---|---|
| `list_strategies` | Lists registered strategies from `backtesting-engine`'s strategy registry. Pure Python, no kdb+ call. |
| `get_price_data` | Reads OHLCV rows for a ticker/date range from the kdb+ `prices` table. |
| `run_q_analytics` | Runs a native q analytics function (`.strategy.sma`, `.strategy.returns`, `.risk.drawdown`) against a ticker's close prices. |
| `run_backtest` | Runs a full backtest via `backtesting-engine`'s `run_backtest()`, including the lookahead-safe kdb+ execution-price join. **Auto-logs every run** to `run_history` (see `session_id` note below). |
| `get_run_history` | Reads all runs for a given `session_id` from `run_history`. |
| `compare_runs` | Reads multiple specific runs by `run_id` from `run_history`, for side-by-side comparison. |

Each follows the repo's `_template.py` convention exactly: an `_impl` async function doing the real work (wrapped in try/except, returning `{"status": "success"/"error", ...}`), and a `register_tools(mcp_server)` function using `@mcp_server.tool()` with a full docstring (this docstring is what the LLM sees as the tool's schema/description — kept detailed and accurate for that reason).

## Dependency on `backtesting-engine`

These tools import from a **separate repo**, [`backtesting-engine`](../../backtesting-engine) (path relative to this fork's expected sibling layout), wired in as a `uv` local path dependency:

```toml
[project]
dependencies = [
    ...
    "backtesting-engine",
]

[tool.uv.sources]
backtesting-engine = { path = "../backtesting-engine", editable = true }
```

**This is not currently upstreamable as a PR to KX's repo as-is** — the path dependency points at a local sibling folder that only exists on a machine with both repos cloned side by side. KX's CI, or anyone else cloning just this fork, would have no such folder. To make this genuinely PR-able, `backtesting-engine` would need to be published as a real package (e.g. to PyPI) first, or its logic would need to be inlined directly into this fork (which would give up the "separate, independently reusable" design). Flagging this honestly rather than implying a PR is a trivial next step.

## `session_id` — a resolved gap in the original spec

The original architecture only specified `run_backtest(strategy, params, ticker, start, end)`, but `run_history`'s schema (and `get_run_history`) both need a `session_id` to group an agent's iteration loop. This fork adds `session_id` as an **optional** parameter: if omitted, a UUID is generated and returned in the result; if you're running a multi-call agent loop, generate one `session_id` yourself and pass it to every `run_backtest` call in that loop so `get_run_history`/`compare_runs` can group them correctly.

## `open_position_at_end`

`run_backtest`'s result includes `open_position_at_end` (bool), computed directly from the final row of the execution-signal series — **not** inferred from trade count. A strategy can legitimately show `trade_summary.total_trades: 0` while still holding a real, still-open position when the backtest window ends (e.g. a trend-follower that entered late and never got an exit signal) — `total_trades` only counts *closed* round-trips. Always check `open_position_at_end` rather than assuming zero trades means the strategy did nothing. This field was added specifically because, without it, both a human and the agent (in early testing) repeatedly misread `0 trades` as a bug.

## Setup

See the main [README](../README.md) for base server setup. Additionally:

1. Clone `backtesting-engine` as a **sibling directory** to this fork (both under the same parent folder), matching the `../backtesting-engine` path in `pyproject.toml`.
2. Follow `backtesting-engine`'s own README to install it and populate the `prices` table.
3. From this fork's root: `uv sync` — should show `backtesting-engine` installed in editable mode.
4. Make sure your q session has `strategy.q`/`history.q` loaded (see `docs/gotchas.md` — this is easy to forget after any restart) before starting `uv run mcp-server`.
5. Start the server: `uv run mcp-server`. You should see **9 tools** registered in the startup log (3 original + 6 new).

See `docs/gotchas.md` for the operational traps we hit building this (hyphens in symbols, function-vs-data persistence, terminal ownership under VS Code/WSL, etc.) — worth reading once before you hit the same ones.

See `docs/agent.md` for how to actually drive an autonomous iteration loop using these tools.
