from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Todo:
    id: int
    title: str
    done: bool = False
    priority: Priority = Priority.MEDIUM
    category_id: int | None = None
    created_at: datetime = field(default_factory=datetime.now)
