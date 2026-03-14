"""Admin dashboard — touches many layers."""

from services.product_service import ProductService
from services.order_service import OrderService
from services.user_service import UserService
from models.product import Product
from models.order import Order
from models.user import User
from data.product_repo import ProductRepository  # VIOLATION: layer skip
from api.inventory_client import InventoryClient  # VIOLATION: layer skip


class AdminDashboard:
    products: ProductService
    orders: OrderService
    users: UserService
    repo: ProductRepository  # VIOLATION: owns data-layer class
    inventory: InventoryClient  # VIOLATION: owns networking-layer class

    def render_stats(self) -> str:
        return "<h1>Admin Dashboard</h1>"
