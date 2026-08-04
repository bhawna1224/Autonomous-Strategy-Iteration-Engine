# Operational Gotchas — Autonomous Strategy Iteration Engine

Hard-won lessons from building and testing this project (kdb+/KDB-X + this MCP server fork + the `backtesting-engine` integration + the agent prompt). Read this before setting up on a new machine, or after any restart — several of these will silently reappear.

## 1. Function definitions do NOT persist across a q restart — table DATA does (sometimes)

- `run_history` (this fork's agent-memory table) is explicitly designed to survive restarts: every write also saves to disk (`.history.log_run` calls `.history.path set run_history` on every insert), and re-running `\l history.q` reloads it from disk automatically.
- The `prices` table does **not** persist — it's in-memory only, populated by `data/ingest_historical.py`. Gone after every restart, no warning.
- The **functions themselves** (`.strategy.sma`, `.risk.drawdown`, `.risk.asof_signal_join`, `.history.log_run`, etc.) also do **not** persist — only exist in memory until you `\l strategy.q` / `\l history.q` again.
- **Symptom if you forget**: `run_backtest()` fails with a terse error whose message is literally just the function's dotted name (e.g. `.risk.asof_signal_join`) — that's q's way of saying "undefined," not a real logic error. If you see this, reload both `.q` files before debugging anything else.

**Checklist after every kdb+ restart:**
```q
.ai:use`kx.ai
.s.init[]
\l /path/to/asie_q/strategy.q
\l /path/to/asie_q/history.q
```
Then re-run `data/ingest_historical.py` for whatever ticker/range you need — `prices` will be empty.

## 2. Hyphens break q symbols and paths — use underscores

q's tokenizer reads a bare hyphen inside a backtick-symbol or path as **subtraction**, not a literal character. This bit us twice:
- A kdb+ database directory named `asie-q` failed to load (`'/ ` error) until renamed to `asie_q`.
- Querying `run_history` by a UUID `session_id` directly in q — `` `eb5ea696-4f2a-... `` — fails the same way, since UUIDs contain hyphens. Fix: build the symbol from a string instead: `` `$"eb5ea696-4f2a-..." ``.

This does **not** affect the Python/pykx tool layer (`get_run_history`, `compare_runs`) — they use `kx.SymbolAtom(...)`/`kx.toq(...)` for proper typed conversion, which bypasses the tokenizer issue entirely. It only bites when a human (or an agent that drops into raw `kdbx_run_sql_query` instead of the purpose-built tools) types a hyphenated value directly into q source.

**Rule of thumb: avoid hyphens in any kdb+-related directory/table/file name. When you must query a hyphenated value in raw q, wrap it as `` `$"..." `` rather than a bare backtick-token.**

## 3. Long-running services must NOT live in VS Code's integrated terminal

`File > Open Folder` in VS Code reloads the whole window — killing every integrated terminal tied to it, including a live q session or `uv run mcp-server`. Run both in a standalone WSL terminal (Windows Terminal / `wsl` from the Start menu), never inside VS Code's own terminal panel. Keep VS Code purely as an editor.

## 4. q session vs. bash terminal — don't mix commands between them

Easy to lose track of which terminal is which, especially with several open at once. `q)` prompt = q code only. Plain `~$` prompt = bash only. Typing a bash command at `q)` (or vice versa) produces confusing errors, not a clean "wrong shell" message.

## 5. Claude Desktop's `claude_desktop_config.json` — `mcpServers` is TOP-LEVEL, not nested

On at least one Claude Desktop build (Microsoft Store / packaged version), `Settings > Developer > Edit Config` opens a single JSON file that *also* contains internal app-state/UI preferences (`epitaxyPrefs`, `sidebarMode`, etc.). `mcpServers` must be a top-level sibling key of `preferences` — nesting it inside `preferences` (or anywhere else) silently does nothing; the server won't show as connected and there's no error telling you why.

## 6. `yfinance` "possibly delisted" is often a transient false alarm

Seen with a valid, actively-traded ticker (AAPL) on a request that worked moments later on retry, while an unrelated ticker succeeded on the identical date range in between. Don't assume the ticker/range is actually wrong — retry once, and cross-check with a different ticker or a smaller range if it persists.

## 7. `ingest_historical.py` does not deduplicate

Re-running it for an overlapping date range appends duplicate rows rather than replacing them. Clear `prices` in q first (`delete from \`prices`) if you need a clean re-ingest of the same range.

## 8. Multi-line paste into an interactive REPL (q or Python) can silently corrupt input

Both q's `q)` prompt and a bare `python` REPL can fail on multi-line paste — either erroring in a confusing way (q) or just hanging on a `...` continuation prompt forever (Python), with no output at all. Prefer writing to a `.q` / `.py` file and loading/running it (`\l file.q`, `python file.py`) over pasting multi-line code directly into either REPL.

## 9. Drawdown sign convention differs between kdb+ and the Python layer

`.risk.drawdown` (q) returns **negative** values (e.g. `-0.18`). `PerformanceAnalyzer.calculate_max_drawdown()` (Python, used by `run_backtest()`) returns a **positive magnitude** (`0.18`). Both are internally consistent on their own; don't compare them directly without accounting for the sign flip.

## 10. `session_id` was not in the original tool signature spec — resolved as an optional param

The original architecture doc specified `run_backtest(strategy, params, ticker, start, end)` with no `session_id`, but `run_history`'s schema and `get_run_history(session_id)` both require one to group an agent's iteration loop. Resolved by making `session_id` an **optional** parameter on the `run_backtest` MCP tool — auto-generates a UUID if omitted, and the tool logs to `run_history` automatically on every call. If you ever change this contract, note that the agent prompt (`docs/agent.md`) depends on generating one `session_id` per goal and reusing it across every `run_backtest` call in that loop.
