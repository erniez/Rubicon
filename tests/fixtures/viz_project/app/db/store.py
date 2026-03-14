"""Data layer — store module."""


class Store:
    """Key-value store for cached data."""

    def __init__(self) -> None:
        self.data: dict = {}

    def get(self, key: str) -> str:
        return self.data.get(key, "")

    def put(self, key: str, value: str) -> None:
        self.data[key] = value
