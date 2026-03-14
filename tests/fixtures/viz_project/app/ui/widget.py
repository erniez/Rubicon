"""Presentation layer — widget module."""

from app.models.order import Order


class Widget:
    """Widget displaying order information."""

    def __init__(self) -> None:
        self.order: Order = Order()

    def display(self) -> str:
        return f"Widget for order {self.order.id}"
