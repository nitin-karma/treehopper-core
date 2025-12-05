# treehopper/agent_base.py
import asyncio
from typing import Optional

from treehopper.treehopper_cancellation import is_run_cancelled
from treehopper.runtime_context import get_run_id


class TreehopperAgentBase:
    """
    Base utility class for agents to get cooperative cancellation support.

    Usage:
      class MyAgent(TreehopperAgentBase):
          async def run(self, ...):
              for i in range(10):
                  await self.cancelable_sleep(1.0)
                  ...
    """

    async def check_cancel(self, run_id: Optional[str] = None) -> None:
        """
        Raise asyncio.CancelledError if the run has been cancelled.
        """
        rid = run_id or get_run_id()
        if not rid:
            return
        if await is_run_cancelled(rid):
            # raise CancelledError to unwind and let wrapper handle logging
            raise asyncio.CancelledError()

    async def cancelable_sleep(
        self, seconds: float, run_id: Optional[str] = None
    ) -> None:
        """
        Sleep with frequent cancellation checks. Granularity is 0.1s.
        """
        # break into 0.1s ticks for responsive checking
        ticks = max(1, int(seconds / 0.1))
        interval = seconds / ticks
        for _ in range(ticks):
            await asyncio.sleep(interval)
            await self.check_cancel(run_id)
