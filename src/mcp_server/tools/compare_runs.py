import logging
import uuid
from typing import Dict, Any, List
import pykx as kx
from mcp_server.utils.kdbx import get_kdb_connection

logger = logging.getLogger(__name__)


async def compare_runs_impl(run_ids: List[str]) -> Dict[str, Any]:
    try:
        if not run_ids:
            return {"status": "error", "message": "run_ids must be a non-empty list of run_id strings."}

        guid_list = [uuid.UUID(r) for r in run_ids]

        conn = get_kdb_connection()
        result = conn(".history.compare", kx.toq(guid_list))
        df = result.pd()

        if df.empty:
            return {"status": "success", "data": [], "message": "No matching runs found."}

        for col in ("run_id", "session_id", "strategy", "ticker"):
            if col in df.columns:
                df[col] = df[col].astype(str)
        for col in ("timestamp", "start_date", "end_date"):
            if col in df.columns:
                df[col] = df[col].astype(str)

        return {"status": "success", "data": df.to_dict(orient="records")}

    except Exception as e:
        logger.error(f"compare_runs failed: {e}")
        return {"status": "error", "message": str(e)}


def register_tools(mcp_server):
    @mcp_server.tool()
    async def compare_runs(run_ids: List[str]) -> Dict[str, Any]:
        """
        Compare multiple backtest runs side by side, by run_id, from the
        kdb+ run_history table. Use this at the end of an agent iteration
        loop to identify the best-performing run.

        Args:
            run_ids (List[str]): List of run_id strings (as returned by run_backtest).

        Returns:
            Dict[str, Any]: {"status", "data": [...]} — one row per run_id found,
            same shape as get_run_history.
        """
        return await compare_runs_impl(run_ids=run_ids)

    return ['compare_runs']
