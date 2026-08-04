import logging
from typing import Dict, Any
import pykx as kx
from mcp_server.utils.kdbx import get_kdb_connection

logger = logging.getLogger(__name__)


async def get_run_history_impl(session_id: str) -> Dict[str, Any]:
    try:
        conn = get_kdb_connection()
        result = conn(".history.get_by_session", kx.SymbolAtom(session_id))
        df = result.pd()

        if df.empty:
            return {
                "status": "success",
                "data": [],
                "message": f"No runs found for session '{session_id}'.",
            }

        for col in ("run_id", "session_id", "strategy", "ticker"):
            if col in df.columns:
                df[col] = df[col].astype(str)
        for col in ("timestamp", "start_date", "end_date"):
            if col in df.columns:
                df[col] = df[col].astype(str)

        return {"status": "success", "data": df.to_dict(orient="records")}

    except Exception as e:
        logger.error(f"get_run_history failed: {e}")
        return {"status": "error", "message": str(e)}


def register_tools(mcp_server):
    @mcp_server.tool()
    async def get_run_history(session_id: str) -> Dict[str, Any]:
        """
        Retrieve all backtest runs logged under a given session_id, from
        the kdb+ run_history table. Use this before proposing new
        parameters, to check what's already been tried in this session.

        Args:
            session_id (str): The session_id returned by a prior run_backtest call.

        Returns:
            Dict[str, Any]: {"status", "data": [...]}, where each row has
            run_id, session_id, timestamp, strategy, ticker, start_date,
            end_date, sharpe, max_drawdown, total_return, params_raw
            (JSON string), metrics_raw (JSON string).
        """
        return await get_run_history_impl(session_id=session_id)

    return ['get_run_history']
