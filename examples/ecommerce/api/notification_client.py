"""Email/SMS notification client."""

from models.order import Order


class NotificationClient:
    def send_confirmation(self, order: Order) -> None:
        pass

    def send_shipping_update(self, order: Order) -> None:
        pass
