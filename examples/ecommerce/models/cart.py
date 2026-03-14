"""Cart item model."""

from models.base import BaseModel


class CartItem(BaseModel):
    product_id: str
    quantity: int
    price: float
