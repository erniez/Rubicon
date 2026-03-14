"""Base model with common functionality."""


class BaseModel:
    id: str = ""

    def to_dict(self) -> dict:
        return vars(self)
