from models.category import Category
from services.todo_service import TodoService


class CategoryStore:
    def __init__(self, todo_service: TodoService) -> None:
        self._categories: dict[int, Category] = {}
        self._next_id: int = 1
        self._todo_service = todo_service

    def add(self, name: str, color: str = "#808080") -> Category:
        category = Category(id=self._next_id, name=name, color=color)
        self._categories[self._next_id] = category
        self._next_id += 1
        return category

    def get(self, category_id: int) -> Category | None:
        return self._categories.get(category_id)

    def list_all(self) -> list[Category]:
        return list(self._categories.values())

    def delete(self, category_id: int) -> bool:
        if category_id in self._categories:
            del self._categories[category_id]
            return True
        return False
