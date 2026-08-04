import logging
import pandas as pd
from typing import Dict, Any, Optional
from mcp_server.utils.kdbx import get_kdb_connection

logger = logging.getLogger(__name__)

VALID_METRICS = {"sma", "returns", "drawdown"}


async def run_q_analytics_impl(
    ticker: str,
    metric: str,
    window: Optional[int] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        if metric not in VALID_METRICS:
            return {
                "status": "error",
                "message": f"Unknown metric '{metric}'. Must be one of: {sorted(VALID_METRICS)}",
            }
        if metric == "sma" and not window:
            return {
                "status": "error",
                "message": "metric='sma' requires a 'window' parameter (integer, e.g. 20).",
            }

        ticker_u = ticker.upper()
        date_filter = ""
        if start and end:
            start_q = pd.Timestamp(start).strftime("%Y.%m.%d")
            end_q = pd.Timestamp(end).strftime("%Y.%m.%d")
            date_filter = f", date within ({start_q};{end_q})"

        base_select = f"select date,close from prices where ticker=`{ticker_u}{date_filter}"

        if metric == "sma":
            stmt = f"update sma:.strategy.sma[close;{int(window)}] from t"
        elif metric == "returns":
            stmt = "update returns:.strategy.returns[close] from t"
        else:  # drawdown
            stmt = "update drawdown:.risk.drawdown[close] from t"

        # Immediately-invoked lambda: build the price slice into local `t`,
        # then apply the q analytics function. Kept as one self-contained
        # call (rather than composing separate query strings) so operator
        # precedence between select/update can't be misread.
        full_query = f"{{[] t:{base_select}; {stmt}}}[]"

        conn = get_kdb_connection()
        result = conn(full_query)
        df = result.pd()

        if df.empty:
            return {
                "status": "success",
                "data": [],
                "message": f"No price data found for {ticker_u}.",
            }

        df["date"] = df["date"].astype(str)
        return {
            "status": "success",
            "metric": metric,
            "ticker": ticker_u,
            "data": df.to_dict(orient="records"),
        }

    except Exception as e:
        logger.error(f"run_q_analytics failed: {e}")
        return {"status": "error", "message": str(e)}


def register_tools(mcp_server):
    @mcp_server.tool()
    async def run_q_analytics(
        ticker: str,
        metric: str,
        window: Optional[int] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run a native kdb+/q analytics function against a ticker's daily
        close prices and return the resulting time series.

        Args:
            ticker (str): Ticker symbol, e.g. 'AAPL'.
            metric (str): One of 'sma' (simple moving average),
                'returns' (daily returns), 'drawdown' (running
                peak-to-trough drawdown, negative values).
            window (Optional[int]): Required when metric='sma' — the
                moving average window length in trading days.
            start (Optional[str]): Optional start date filter 'YYYY-MM-DD'.
            end (Optional[str]): Optional end date filter 'YYYY-MM-DD'.

        Returns:
            Dict[str, Any]: {"status", "metric", "ticker", "data": [...]}
            where each row has 'date', 'close', and the requested metric column.
        """
        return await run_q_analytics_impl(ticker=ticker, metric=metric, window=window, start=start, end=end)

    return ['run_q_analytics']
