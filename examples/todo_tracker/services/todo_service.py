from data.store import TodoStore
from models.category import Category
from models.todo import Priority, Todo


class TodoService:
    def __init__(self, store: TodoStore) -> None:
        self._store = store

    def create_todo(
        self,
        title: str,
        priority: Priority = Priority.MEDIUM,
        category_id: int | None = None,
    ) -> Todo:
        todo = Todo(id=0, title=title, priority=priority, category_id=category_id)
        return self._store.add(todo)

    def complete_todo(self, todo_id: int) -> Todo | None:
        todo = self._store.get(todo_id)
        if todo is None:
            return None
        todo.done = True
        return self._store.update(todo)

    def list_todos(self, show_done: bool = True) -> list[Todo]:
        todos = self._store.list_all()
        if not show_done:
            todos = [t for t in todos if not t.done]
        return todos

    def list_by_category(self, category_id: int) -> list[Todo]:
        return [t for t in self._store.list_all() if t.category_id == category_id]

    def delete_todo(self, todo_id: int) -> bool:
        return self._store.delete(todo_id)

    def pending_count(self) -> int:
        return len([t for t in self._store.list_all() if not t.done])
