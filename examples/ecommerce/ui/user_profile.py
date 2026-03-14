"""User profile page."""

from services.user_service import UserService
from models.user import User


class UserProfilePage:
    user_service: UserService

    def render(self, user_id: str) -> str:
        user = self.user_service.get_user(user_id)
        return f"<h1>{user.name}</h1><p>{user.email}</p>"
