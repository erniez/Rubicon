from dataclasses import dataclass


@dataclass
class Category:
    id: int
    name: str
    color: str = "#808080"
