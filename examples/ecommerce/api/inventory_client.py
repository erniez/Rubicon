"""External inventory management API."""

from ui.product_page import ProductPage  # VIOLATION: networking -> presentation (upward dependency!)


class InventoryClient:
    page: ProductPage  # VIOLATION: networking owns a presentation class

    def check_stock(self, sku: str) -> int:
        return 42

    def reserve(self, sku: str, quantity: int) -> bool:
        return True
