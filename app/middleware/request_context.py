import contextvars
from uuid import uuid4
from starlette.middleware.base import BaseHTTPMiddleware

_request_context: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "request_context", default={}
)


class RequestContext:
    @staticmethod
    def get(key: str, default=None):
        return _request_context.get().get(key, default)

    @staticmethod
    def set(key: str, value):
        ctx = _request_context.get().copy()
        ctx[key] = value
        _request_context.set(ctx)

    @staticmethod
    def update(data: dict):
        ctx = _request_context.get().copy()
        ctx.update(data)
        _request_context.set(ctx)

    @staticmethod
    def get_store() -> dict:
        return _request_context.get()

    @staticmethod
    def user_id():
        return RequestContext.get("user_id")

    @staticmethod
    def request_id():
        return RequestContext.get("request_id")

    @staticmethod
    def session_id():
        return RequestContext.get("session_id")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        _request_context.set(
            {
                "request_id": str(uuid4()),
                "user_id": getattr(request.state, "user_id", None),
            }
        )
        response = await call_next(request)
        return response


def get_current_user_id() -> int:
    """FastAPI dependency that returns the current user_id from request context."""
    return RequestContext.user_id()
