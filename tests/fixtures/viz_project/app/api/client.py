"""Networking layer — API client module."""

from app.models.user import User


class ApiClient:
    """HTTP client for fetching user data from remote API."""

    def __init__(self) -> None:
        self.base_url: str = "https://api.example.com"

    def fetch_user(self, user_id: int) -> User:
        return User()
