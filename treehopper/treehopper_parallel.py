"""
Parallel runner with concurrency auto-throttle, cancellation support,
async HTTP execution, and full per-run timing.
"""

import asyncio
import time
import os
from typing import Any, Dict, List

from treehopper.treehopper_cancellation import run_with_cancellation
from treehopper.utils import run_registry as run_registry_mod

# Auto-throttle env vars
AUTO_THROTTLE = os.getenv("TH_AUTO_THROTTLE", "1") == "1"
SAFE_CONCURRENCY = int(os.getenv("TH_SAFE_CONCURRENCY", "3"))  # default for OpenAI


# =============================================================================
# PARALLEL EXECUTOR (local async semaphore wrapper)
# =============================================================================
class ParallelExecutor:
    def __init__(self, concurrency: int):
        if concurrency < 1:
            concurrency = 1
        self.sem = asyncio.Semaphore(concurrency)
        self.tasks: List[asyncio.Task] = []

    async def _run_child(self, fn, payload, idx):
        async with self.sem:
            start = time.time()
            try:
                res = await fn(payload)
            except Exception as e:
                res = {"error": f"Executor caught exception: {e}"}
            duration = round(time.time() - start, 3)
            return {"index": idx, "result": res, "duration": duration}

    async def run(self, fn, payloads: List[Any]):
        self.tasks = [
            asyncio.create_task(self._run_child(fn, payloads[i], i))
            for i in range(len(payloads))
        ]
        results = await asyncio.gather(*self.tasks)
        return sorted(results, key=lambda r: r["index"])


# =============================================================================
# SYNC → ASYNC HTTP HELPERS (with cancellation)
# =============================================================================
async def _http_post_json(url: str, payload: dict, headers: dict):
    import httpx

    async with httpx.AsyncClient(timeout=40.0) as client:
        r = await client.post(url, json=payload, headers=headers)
        try:
            return r.json()
        except Exception:
            return {"error": f"HTTP {r.status_code}: {r.text}"}


# =============================================================================
# MAIN LOGIC: parallel_chain_run
# =============================================================================
async def parallel_chain_run(
    ref: str,
    payloads: List[Dict[str, Any]],
    parallel: int,
    concurrency: int,
    detached: bool,
):
    """
    Phase 3.3 — Parallel execution with cancellation.

    For each parallel instance:
      • Creates run_id
      • Registers in cancellation registry
      • Calls either MAIN server chain endpoint or micro-app
      • Returns structured result

    For whole parallel batch:
      • Creates a batch_id and links all run_ids under it
    """

    from treehopper.treehopper_chains import (
        resolve_chain,
        BASE_URL,
        load_chain_cfg,
        chain_run_detached,
        RUNTIME_DIR,
        CHAIN_PID_PREFIX,
        read_pid_and_port,
    )

    chain_ref = resolve_chain(ref)
    chain_name = chain_ref.chain_name
    chain_id = chain_ref.chain_id

    # Ensure payload list length == parallel
    if len(payloads) < parallel:
        last = payloads[-1] if payloads else {}
        payloads = payloads + [last] * (parallel - len(payloads))

    # Auto-throttle: protect from provider rate limits
    provider = os.getenv("TH_LLM_PROVIDER", "openai").lower()
    if AUTO_THROTTLE and provider == "openai":
        if concurrency > SAFE_CONCURRENCY:
            print(
                f"⚠️ Auto-throttling concurrency from {concurrency} → "
                f"{SAFE_CONCURRENCY} (TH_SAFE_CONCURRENCY)"
            )
            concurrency = SAFE_CONCURRENCY

    if concurrency > parallel:
        concurrency = parallel

    # Unique batch ID for this entire run
    batch_id = f"batch-{int(time.time() * 1000)}"
    print(f"📦 batch_id={batch_id}")
    executor = ParallelExecutor(concurrency)

    # Load static chain metadata
    cfg = load_chain_cfg(chain_ref)
    endpoint = cfg.get("endpoint") or f"/api/v1/chains/{chain_name}"
    print(f"Endpoint to call - {endpoint}")

    # ------------------------------------------------------------
    # Single parallel job
    # ------------------------------------------------------------
    async def _run_one(payload):
        run_id = run_registry_mod.make_run_id(chain_name)

        # Compute URL
        if detached:
            # Ensure dedicated chain micro-app exists
            chain_run_detached(chain_ref, payload, run_once=False)
            pid_file = RUNTIME_DIR / f"{CHAIN_PID_PREFIX}{chain_id}.pid"
            _, port = read_pid_and_port(pid_file)
            if not port:
                return {
                    "success": False,
                    "run_id": run_id,
                    "error": "runtime port missing",
                    "duration": 0.0,
                }
            url = f"http://localhost:{port}/api/v1/{chain_name}/run"
        else:
            url = f"{BASE_URL}/api/v1/chains/{chain_name}"

        # Actual HTTP call inside a cancellable wrapper
        async def _coro():
            return await _http_post_json(
                url,
                payload or {},
                {
                    "x-api-key": "demo-key-123",
                    "X-Treehopper-Run-Id": run_id,
                    "X-Treehopper-Batch-Id": batch_id or "",
                },
            )

        start = time.time()
        result = await run_with_cancellation(
            run_id=run_id,
            chain_id=chain_id,
            batch_id=batch_id,
            coro=_coro,
        )
        duration = round(time.time() - start, 3)

        if isinstance(result, dict) and "run_id" not in result:
            result["run_id"] = run_id

        return {
            "success": result.get("success"),
            "run_id": result.get("run_id"),
            "error": result.get("error"),
            "duration": duration,
        }

    # ------------------------------------------------------------
    # Execute all tasks
    # ------------------------------------------------------------
    print(
        f"🌿 Parallel execution: {parallel} runs  "
        f"| concurrency={concurrency} | detached={detached}"
    )
    print(
        f"🌿 Running {parallel} parallel tasks via "
        f"{'DETACHED micro-app' if detached else 'MAIN server'}..."
    )

    results = await executor.run(_run_one, payloads)

    # ------------------------------------------------------------
    # Summary Output
    # ------------------------------------------------------------
    print("\n===== PARALLEL RUN SUMMARY =====")
    total = len(results)
    success_count = 0
    fail_count = 0
    total_time = 0.0

    for i, r in enumerate(results):
        dur = r["duration"]
        total_time += dur
        is_ok = bool(r.get("success"))
        if is_ok is True:
            success_count += 1
        else:
            fail_count += 1

        print(f"[{i}] success={is_ok} run_id={r.get('run_id')}  duration={dur}s")

    avg = round(total_time / total, 3) if total else 0.0

    print("--------------------------------")
    print(f"Runs: {total}  Success: {success_count}  Failures: {fail_count}")
    print(
        f"Avg duration: {avg}s  Total wallclock sum(durations): {round(total_time,3)}s"
    )
    print("--------------------------------")

    return results


# =============================================================================
# ENTRY POINT
# =============================================================================
def parallel_chain_run_entry(ref, payloads, parallel, concurrency, detached):
    asyncio.run(parallel_chain_run(ref, payloads, parallel, concurrency, detached))
