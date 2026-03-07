import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.exceptions import AppException

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            response = await call_next(request)
            return response
        except AppException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"code": 1, "msg": e.message, "data": e.data},
            )
        except Exception as e:
            logger.exception(f"Unhandled error: {e}")
            return JSONResponse(
                status_code=500,
                content={"code": 1, "msg": "Internal server error", "data": None},
            )
