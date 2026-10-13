"""Bound write bodies before form/JSON parsing, including chunked requests."""

import anyio
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_REQUEST_BYTES = 64 * 1024


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in {
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        }:
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        length = headers.get(b"content-length")
        if length is not None:
            try:
                size = int(length)
                if size < 0:
                    raise ValueError("negative content length")
            except ValueError:
                await self._reject(scope, receive, send, 400)
                return
            if size > MAX_REQUEST_BYTES:
                await self._reject(scope, receive, send, 413)
                return
        body = bytearray()
        deadline = anyio.current_time() + 10
        while True:
            try:
                with anyio.fail_after(max(0, deadline - anyio.current_time())):
                    message = await receive()
            except TimeoutError:
                await JSONResponse(
                    {
                        "status": "error",
                        "code": "request_timeout",
                        "message": "请求读取超时",
                    },
                    status_code=408,
                )(scope, receive, send)
                return
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > MAX_REQUEST_BYTES:
                await self._reject(scope, receive, send, 413)
                return
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send, status: int) -> None:
        response = JSONResponse(
            {
                "status": "error",
                "code": "request_too_large" if status == 413 else "invalid_request",
                "message": "请求体过大" if status == 413 else "请求格式无效",
            },
            status_code=status,
        )
        await response(scope, receive, send)
