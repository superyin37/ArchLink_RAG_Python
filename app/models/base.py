from sqlalchemy import Column, Integer, DateTime, func
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class BaseModel(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    create_time = Column(DateTime, server_default=func.now(), nullable=False)
    update_time = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    delete_time = Column(DateTime, nullable=True, default=None)
