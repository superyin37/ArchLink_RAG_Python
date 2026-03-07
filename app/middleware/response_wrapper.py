from starlette.responses import JSONResponse


class R:
    """Unified response builder"""

    @staticmethod
    def success(data=None, msg: str = "success", status_code: int = 200):
        return JSONResponse(
            status_code=status_code,
            content={"code": 0, "msg": msg, "data": data},
        )

    @staticmethod
    def fail(msg: str = "error", data=None, status_code: int = 400):
        return JSONResponse(
            status_code=status_code,
            content={"code": 1, "msg": msg, "data": data},
        )

    @staticmethod
    def page(items: list, total: int, page: int, size: int) -> dict:
        return {
            "code": 0,
            "msg": "success",
            "data": {"list": items, "total": total, "page": page, "size": size},
        }
