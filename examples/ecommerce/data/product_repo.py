"""Product data access."""

from data.base_repo import BaseRepository
from models.product import Product


class ProductRepository(BaseRepository):
    model: Product

    def find_by_id(self, product_id: str) -> Product:
        return Product()

    def search(self, query: str) -> list[Product]:
        return []
