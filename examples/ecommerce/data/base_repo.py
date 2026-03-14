"""Base repository with common CRUD."""


class BaseRepository:
    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass
