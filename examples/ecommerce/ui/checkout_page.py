"""Checkout flow view."""

from services.cart_service import CartService
from services.order_service import OrderService
from models.order import Order
from data.payment_gateway import PaymentGateway  # VIOLATION: presentation -> data (layer skip)


class CheckoutPage:
    cart: CartService
    orders: OrderService
    payments: PaymentGateway  # VIOLATION: owns a data-layer class directly

    def render(self) -> str:
        items = self.cart.get_items()
        total = sum(item.price for item in items)
        return f"<h2>Checkout</h2><p>Total: ${total}</p>"

    def submit_order(self) -> Order:
        order = self.orders.create_order(self.cart.get_items())
        self.payments.charge(order.total)  # Should go through a service!
        return order
