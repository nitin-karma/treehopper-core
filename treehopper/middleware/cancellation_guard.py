import asyncio

# from pathlib import Path
# from treehopper.th_config import CANCEL_DIR
from treehopper.treehopper_cancellation import is_run_cancelled
from treehopper.runtime_context import get_run_id


# ----------------------------------------------------------------------
# INTERNAL: Check cancellation and raise asyncio.CancelledError
# ----------------------------------------------------------------------
async def _check_cancellation(run_id: str):
    """
    Reads FS marker and triggers asyncio.CancelledError if cancelled.
    """
    if await is_run_cancelled(run_id):
        raise asyncio.CancelledError()


# ----------------------------------------------------------------------
# PUBLIC: Cancellable sleep
# ----------------------------------------------------------------------
async def th_sleep(seconds: float):
    """
    Sleep with cancellation checks every 100ms.
    This ensures agent code remains highly responsive to cancellation.
    """
    run_id = get_run_id()
    slice_time = 0.1
    total = int(seconds / slice_time)

    for _ in range(total):
        await asyncio.sleep(slice_time)
        if run_id:
            await _check_cancellation(run_id)


# ----------------------------------------------------------------------
# PUBLIC: Wrap any agent coroutine with cancellation monitoring
# ----------------------------------------------------------------------
async def cancellation_guard(coro, run_id: str, step_index: int):
    """
    Wrap agent execution so cancellation is detected BEFORE, DURING, AFTER.

    • Checks cancel before coroutine starts
    • Checks cancel after every await (via th_sleep)
    • If cancelled, stops chain cleanly with asyncio.CancelledError
    """
    # Before execution
    await _check_cancellation(run_id)

    try:
        result = await coro
    except asyncio.CancelledError:
        print(f"[cancellation_guard] CANCELLED at step={step_index}, run_id={run_id}")
        raise

    # After execution
    await _check_cancellation(run_id)

    return result
