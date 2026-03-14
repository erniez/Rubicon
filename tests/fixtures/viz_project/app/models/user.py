"""Domain layer — user model."""


class User:
    """Core user domain model."""

    def __init__(self) -> None:
        self.name: str = ""
        self.email: str = ""
