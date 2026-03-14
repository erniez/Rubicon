"""Order processing logic."""

from models.order import Order
from models.cart import CartItem
from data.order_repo import OrderRepository
from api.notification_client import NotificationClient  # domain -> networking: allowed (downward)


class OrderService:
    repo: OrderRepository
    notifications: NotificationClient

    def create_order(self, items: list[CartItem]) -> Order:
        order = Order(items=items, total=sum(i.price for i in items))
        self.repo.save(order)
        self.notifications.send_confirmation(order)
        return order
