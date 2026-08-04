import logging
import uuid
import datetime
from typing import Dict, Any, Optional
import pykx as kx
from mcp_server.utils.kdbx import get_kdb_connection, db_config
from run_backtest import run_backtest as run_backtest_lib

logger = logging.getLogger(__name__)


async def run_backtest_impl(
    strategy: str,
    params: Optional[Dict[str, Any]],
    ticker: str,
    start: str,
    end: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        params = params or {}
        sid = session_id or str(uuid.uuid4())

        result = run_backtest_lib(
            strategy=strategy,
            params=params,
            ticker=ticker,
            start=start,
            end=end,
            host=db_config.host,
            port=db_config.port,
        )

        metrics = {
            "sharpe": result["sharpe"],
            "max_drawdown": result["max_drawdown"],
            "total_return": result["total_return"],
            "win_rate": float(result["trade_summary"].get("win_rate", 0.0)),
            "total_trades": float(result["trade_summary"].get("total_trades", 0)),
        }

        conn = get_kdb_connection()
        run_id_result = conn(
            ".history.log_run",
            kx.SymbolAtom(sid),
            kx.SymbolAtom(strategy),
            kx.SymbolAtom(ticker.upper()),
            datetime.date.fromisoformat(start),
            datetime.date.fromisoformat(end),
            kx.toq(params),
            kx.toq(metrics),
        )

        result["session_id"] = sid
        result["run_id"] = str(run_id_result.py())

        return {"status": "success", **result}

    except Exception as e:
        logger.error(f"run_backtest tool failed: {e}")
        return {"status": "error", "message": str(e)}


def register_tools(mcp_server):
    @mcp_server.tool()
    async def run_backtest(
        strategy: str,
        params: Optional[Dict[str, Any]],
        ticker: str,
        start: str,
        end: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run a full vectorized backtest for a registered strategy against
        historical kdb+ price data, with lookahead-safe execution pricing.
        Automatically logs the run to run_history (queryable later via
        get_run_history / compare_runs).

        Args:
            strategy (str): Registered strategy name. Use list_strategies
                to see available options (e.g. 'ma_crossover', 'rsi').
            params (Optional[Dict[str, Any]]): Strategy-specific parameters,
                e.g. {"short_window": 10, "long_window": 50} for ma_crossover,
                or {"period": 14, "oversold": 30, "overbought": 70} for rsi.
            ticker (str): Ticker symbol, e.g. 'AAPL'.
            start (str): Start date, 'YYYY-MM-DD'.
            end (str): End date, 'YYYY-MM-DD'.
            session_id (Optional[str]): Groups multiple runs under one
                agent goal-seeking loop. If omitted, a new session_id is
                generated and returned — pass it back in on subsequent
                calls within the same iteration loop to group them.

        Returns:
            Dict[str, Any]: status, session_id, run_id, sharpe, max_drawdown,
            total_return, annualized_return, annualized_volatility,
            trade_summary, open_position_at_end, trade_log, equity_curve.

            NOTE on open_position_at_end: a strategy can have 0 CLOSED
            trades in trade_summary while still holding an open position
            when the window ends (e.g. a trend-follower that entered late
            and never exited) — this is valid, not a bug. Check
            open_position_at_end (true/false) rather than assuming
            trade_summary.total_trades == 0 means "never traded."
        """
        return await run_backtest_impl(
            strategy=strategy, params=params, ticker=ticker, start=start, end=end, session_id=session_id
        )

    return ['run_backtest']
