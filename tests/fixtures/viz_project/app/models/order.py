"""Domain layer — order model."""

from app.db.repo import Repo


class Order:
    """Core order domain model."""

    def __init__(self) -> None:
        self.id: int = 0
        self.repo: Repo = Repo()
