from services.todo_service import TodoService
from models.todo import Priority, Todo
from models.category import Category
from data.category_store import CategoryStore


class TodoApp:
    def __init__(self, service: TodoService, category_store: CategoryStore) -> None:
        self._service = service
        self._category_store = category_store

    def add(self, title: str, priority: str = "medium", category_id: int | None = None) -> str:
        pri = Priority(priority)
        todo = self._service.create_todo(title, pri, category_id=category_id)
        return f"Created: [{todo.id}] {todo.title} ({todo.priority.value})"

    def done(self, todo_id: int) -> str:
        todo = self._service.complete_todo(todo_id)
        if todo is None:
            return f"Todo {todo_id} not found"
        return f"Completed: [{todo.id}] {todo.title}"

    def list(self, all: bool = False) -> str:
        todos = self._service.list_todos(show_done=all)
        if not todos:
            return "No todos found"
        return "\n".join(_format_todo(t, self._category_store) for t in todos)

    def list_by_category(self, category_id: int) -> str:
        category = self._category_store.get(category_id)
        if category is None:
            return f"Category {category_id} not found"
        todos = self._service.list_by_category(category_id)
        if not todos:
            return f"No todos in '{category.name}'"
        header = f"── {category.name} ──"
        lines = [_format_todo(t, self._category_store) for t in todos]
        return header + "\n" + "\n".join(lines)

    def add_category(self, name: str, color: str = "#808080") -> str:
        category = self._category_store.add(name, color)
        return f"Created category: [{category.id}] {category.name}"

    def list_categories(self) -> str:
        categories = self._category_store.list_all()
        if not categories:
            return "No categories"
        return "\n".join(f"[{c.id}] {c.name}" for c in categories)

    def remove(self, todo_id: int) -> str:
        if self._service.delete_todo(todo_id):
            return f"Deleted todo {todo_id}"
        return f"Todo {todo_id} not found"

    def status(self) -> str:
        pending = self._service.pending_count()
        return f"{pending} todo(s) remaining"


def _format_todo(todo: Todo, category_store: CategoryStore) -> str:
    check = "x" if todo.done else " "
    cat_label = ""
    if todo.category_id is not None:
        cat = category_store.get(todo.category_id)
        if cat is not None:
            cat_label = f" [{cat.name}]"
    return f"[{check}] {todo.id}. {todo.title} ({todo.priority.value}){cat_label}"
