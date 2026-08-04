import logging
import pandas as pd
from typing import Dict, Any
from mcp_server.utils.kdbx import get_kdb_connection

logger = logging.getLogger(__name__)
MAX_ROWS_RETURNED = 2000


async def get_price_data_impl(ticker: str, start: str, end: str) -> Dict[str, Any]:
    try:
        ticker_u = ticker.upper()
        start_q = pd.Timestamp(start).strftime("%Y.%m.%d")
        end_q = pd.Timestamp(end).strftime("%Y.%m.%d")

        query = (
            f"select date,open,high,low,close,volume from prices "
            f"where ticker=`{ticker_u}, date within ({start_q};{end_q})"
        )

        conn = get_kdb_connection()
        result = conn(query)
        df = result.pd()

        if df.empty:
            return {
                "status": "success",
                "data": [],
                "message": f"No price data found for {ticker_u} between {start} and {end}.",
            }

        df["date"] = df["date"].astype(str)
        total = len(df)
        truncated = df.head(MAX_ROWS_RETURNED)

        response = {"status": "success", "data": truncated.to_dict(orient="records")}
        if total > MAX_ROWS_RETURNED:
            response["message"] = f"Showing first {MAX_ROWS_RETURNED} of {total} rows"
        return response

    except Exception as e:
        logger.error(f"get_price_data failed: {e}")
        return {"status": "error", "message": str(e)}


def register_tools(mcp_server):
    @mcp_server.tool()
    async def get_price_data(ticker: str, start: str, end: str) -> Dict[str, Any]:
        """
        Retrieve historical daily OHLCV price data for a ticker from the
        kdb+ `prices` table.

        Args:
            ticker (str): Ticker symbol, e.g. 'AAPL'. Case-insensitive.
            start (str): Start date, 'YYYY-MM-DD'.
            end (str): End date, 'YYYY-MM-DD'.

        Returns:
            Dict[str, Any]: {"status": "success"/"error", "data": [...], "message": optional str}
            Each row in "data" has: date, open, high, low, close, volume.
        """
        return await get_price_data_impl(ticker=ticker, start=start, end=end)

    return ['get_price_data']
