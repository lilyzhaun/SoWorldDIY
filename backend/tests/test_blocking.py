import time

import anyio

from app.blocking import run_blocking


def test_slow_sync_call_does_not_block_event_loop():
    async def scenario():
        ran = []

        async def upstream():
            await run_blocking(time.sleep, 0.2)
            ran.append("upstream")

        async def health():
            await anyio.sleep(0.02)
            ran.append("health")

        async with anyio.create_task_group() as group:
            group.start_soon(upstream)
            group.start_soon(health)
        assert ran == ["health", "upstream"]

    anyio.run(scenario)
