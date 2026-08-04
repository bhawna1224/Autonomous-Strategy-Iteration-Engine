import logging
from typing import Dict, Any
from strategies.registry import list_strategies as list_strategies_lib

logger = logging.getLogger(__name__)


async def list_strategies_impl() -> Dict[str, Any]:
    try:
        return {"status": "success", "strategies": list_strategies_lib()}
    except Exception as e:
        logger.error(f"list_strategies failed: {e}")
        return {"status": "error", "message": str(e)}


def register_tools(mcp_server):
    @mcp_server.tool()
    async def list_strategies() -> Dict[str, Any]:
        """
        List all strategies currently registered in the strategy registry
        and available to run_backtest.

        Returns:
            Dict[str, Any]: {"status": "success", "strategies": [str, ...]}
        """
        return await list_strategies_impl()

    return ['list_strategies']
