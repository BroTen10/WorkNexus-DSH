import uuid

from sqlalchemy.orm import DeclarativeBase


def uuid_str() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass
