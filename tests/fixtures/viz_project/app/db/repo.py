"""Data layer — repository module."""

from app.ui.screen import Screen


class Repo:
    """Data access repository.

    Imports from presentation layer — this is a violation.
    """

    def __init__(self) -> None:
        self.screen: Screen = Screen()

    def save(self, data: dict) -> None:
        pass
