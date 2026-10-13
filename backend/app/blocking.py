"""Run the existing sync clients off the event loop with bounded concurrency."""

from collections.abc import Callable
from functools import partial
from typing import ParamSpec, TypeVar

import anyio
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

P = ParamSpec("P")
T = TypeVar("T")
_workers = anyio.CapacityLimiter(8)
_requests = anyio.CapacityLimiter(32)


async def run_blocking(fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    # Do not abandon a running financial operation on cancellation and imply it
    # never happened. No automatic retry is performed.
    return await anyio.to_thread.run_sync(
        partial(fn, *args, **kwargs), limiter=_workers
    )


class RequestConcurrencyMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") == "/_health":
            await self.app(scope, receive, send)
            return
        try:
            with anyio.fail_after(0.5):
                await _requests.acquire()
        except TimeoutError:
            await JSONResponse(
                {
                    "status": "error",
                    "code": "service_busy",
                    "message": "服务繁忙，请稍后重试",
                },
                status_code=503,
            )(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        finally:
            _requests.release()
