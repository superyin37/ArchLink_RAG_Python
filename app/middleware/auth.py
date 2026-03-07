import re
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.core.jwt import decode_token

AUTH_WHITELIST = [
    {"path": "/health", "methods": []},
    {"path": "/api/health", "methods": []},
    {"path": "/ping", "methods": []},
    {"path": "/api/rag/provider/supported", "methods": ["GET"]},
    {"path": "/api/rag/provider/vector-db-types", "methods": ["GET"]},
    {"path": "/api/llm/provider", "methods": ["GET"]},
    {"path": "/api/llm/model", "methods": ["GET"]},
    {"path": "/api/llm/model/by-provider", "methods": ["GET"]},
    {"path": "/api/auth/**", "methods": ["POST"]},
    {"path": "/uploads/**", "methods": ["GET"]},
    {"path": "/test/**", "methods": []},
    {"path": "/api/webhook/**", "methods": ["POST"]},
    # Temporarily allow all API routes during development
    {"path": "/api/**", "methods": []},
    {"path": "/docs", "methods": []},
    {"path": "/openapi.json", "methods": []},
    {"path": "/redoc", "methods": []},
]


def match_path(request_path: str, pattern: str) -> bool:
    pattern_parts = pattern.split("/")
    path_parts = request_path.split("/")

    for i, pp in enumerate(pattern_parts):
        if pp == "**":
            return True
        if i >= len(path_parts):
            return False
        if pp == "*":
            continue
        if pp.startswith(":"):
            continue
        if pp != path_parts[i]:
            return False

    return len(pattern_parts) == len(path_parts)


def is_whitelisted(path: str, method: str) -> bool:
    for rule in AUTH_WHITELIST:
        if match_path(path, rule["path"]):
            if not rule["methods"] or method.upper() in rule["methods"]:
                return True
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        token = request.headers.get("token") or request.headers.get(
            "authorization", ""
        ).replace("Bearer ", "")
        user_id = None

        if token:
            payload = decode_token(token)
            if payload:
                user_id = payload.get("user_id")

        request.state.user_id = user_id

        if is_whitelisted(request.url.path, request.method):
            return await call_next(request)

        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"code": 1, "msg": "Unauthorized", "data": None},
            )

        return await call_next(request)
