"""Shopping cart logic."""

from models.product import Product
from models.cart import CartItem
from data.cart_repo import CartRepository


class CartService:
    repo: CartRepository

    def add_item(self, product_id: str) -> None:
        self.repo.add(product_id)

    def get_items(self) -> list[CartItem]:
        return self.repo.get_all()

    def clear(self) -> None:
        self.repo.clear()
