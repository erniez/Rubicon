"""Cart data access."""

from data.base_repo import BaseRepository
from models.cart import CartItem


class CartRepository(BaseRepository):
    model: CartItem

    def add(self, product_id: str) -> None:
        pass

    def get_all(self) -> list[CartItem]:
        return []

    def clear(self) -> None:
        pass
