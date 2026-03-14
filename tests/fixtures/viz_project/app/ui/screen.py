"""Presentation layer — screen module."""

from app.models.user import User


class Screen:
    """Main screen that displays user data."""

    def __init__(self) -> None:
        self.user: User = User()

    def render(self) -> str:
        return f"Screen for {self.user.name}"
