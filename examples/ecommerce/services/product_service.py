"""Product business logic."""

from models.product import Product
from data.product_repo import ProductRepository


class ProductService:
    repo: ProductRepository

    def get_product(self, product_id: str) -> Product:
        return self.repo.find_by_id(product_id)

    def search(self, query: str) -> list[Product]:
        return self.repo.search(query)
