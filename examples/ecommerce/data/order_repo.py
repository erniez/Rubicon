"""Order data access."""

from data.base_repo import BaseRepository
from models.order import Order


class OrderRepository(BaseRepository):
    model: Order

    def save(self, order: Order) -> None:
        pass

    def find_by_user(self, user_id: str) -> list[Order]:
        return []
