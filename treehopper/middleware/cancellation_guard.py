import asyncio
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
# PUBLIC: Cancellable sleep (robust)
# ----------------------------------------------------------------------
async def th_sleep(seconds: float):
    """
    Sleep in small slices and check cancellation after each slice.
    Guarantees at least one await even for small durations.
    """
    run_id = get_run_id()

    # Minimum slice granularity
    slice_time = 0.1

    if seconds <= slice_time:
        # One-shot sleep with cancel check
        await asyncio.sleep(seconds)
        if run_id:
            await _check_cancellation(run_id)
        return

    # Multi-slice sleep
    remaining = seconds
    while remaining > 0:
        step = min(slice_time, remaining)
        await asyncio.sleep(step)
        remaining -= step
        if run_id:
            await _check_cancellation(run_id)


# ----------------------------------------------------------------------
# PUBLIC: Inject cancellation awareness into ANY coroutine
# ----------------------------------------------------------------------
async def _inject_yield():
    """
    Ensures at least one event-loop switch before/after user coroutine.
    Important because some agent code may start running synchronously
    before the runtime can notice a cancel request.
    """
    await asyncio.sleep(0)


# ----------------------------------------------------------------------
# PUBLIC: cancellation-guard wrapper
# ----------------------------------------------------------------------
async def cancellation_guard(coro, run_id: str, step_index: int):
    """
    • Checks cancel BEFORE starting user coroutine
    • Forces a yield to ensure runtime has time to read cancel file
    • Awaits the coroutine
    • Checks cancel AFTER execution

    The agent itself must use th_sleep() for mid-work checks.
    """
    # Pre-cancel
    await _check_cancellation(run_id)

    # Yield so FS cancel markers can be observed before agent code enters heavy loop
    await _inject_yield()

    try:
        result = await coro
    except asyncio.CancelledError:
        print(f"[cancellation_guard] CANCELLED at step={step_index}, run_id={run_id}")
        raise

    # Post-cancel
    await _check_cancellation(run_id)

    return result
