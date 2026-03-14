"""User account management."""

from models.user import User
from data.user_repo import UserRepository


class UserService:
    repo: UserRepository

    def get_user(self, user_id: str) -> User:
        return self.repo.find_by_id(user_id)

    def update_email(self, user_id: str, email: str) -> None:
        user = self.repo.find_by_id(user_id)
        user.email = email
        self.repo.save(user)
