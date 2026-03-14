"""User data access."""

from data.base_repo import BaseRepository
from models.user import User


class UserRepository(BaseRepository):
    model: User

    def find_by_id(self, user_id: str) -> User:
        return User()

    def save(self, user: User) -> None:
        pass
