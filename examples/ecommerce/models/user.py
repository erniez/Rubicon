"""User domain model."""

from models.base import BaseModel


class User(BaseModel):
    name: str
    email: str
    role: str
