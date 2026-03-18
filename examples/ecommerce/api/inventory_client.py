"""External inventory management API."""

class InventoryClient:

    def check_stock(self, sku: str) -> int:
        return 42

    def reserve(self, sku: str, quantity: int) -> bool:
        return True
