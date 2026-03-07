from typing import Any, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class PageRequest(BaseModel):
    page: int = 1
    size: int = 10


class PageResponse(BaseModel, Generic[T]):
    list: list[T]
    total: int
    page: int
    size: int


class SuccessResponse(BaseModel):
    code: int = 0
    msg: str = "success"
    data: Any = None


class IdResponse(BaseModel):
    id: int
