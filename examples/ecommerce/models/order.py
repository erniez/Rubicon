"""Order domain model."""

from models.base import BaseModel
from models.cart import CartItem


class Order(BaseModel):
    items: list[CartItem]
    total: float
    status: str = "pending"
