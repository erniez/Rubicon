"""Product detail page view."""

from services.product_service import ProductService
from services.cart_service import CartService
from models.product import Product


class ProductPage:
    service: ProductService
    cart: CartService

    def render(self, product_id: str) -> str:
        product = self.service.get_product(product_id)
        return f"<h1>{product.name}</h1><p>${product.price}</p>"

    def add_to_cart(self, product_id: str) -> None:
        self.cart.add_item(product_id)
