from models.todo import Todo


class TodoStore:
    def __init__(self) -> None:
        self._todos: dict[int, Todo] = {}
        self._next_id: int = 1

    def add(self, todo: Todo) -> Todo:
        todo.id = self._next_id
        self._todos[self._next_id] = todo
        self._next_id += 1
        return todo

    def get(self, todo_id: int) -> Todo | None:
        return self._todos.get(todo_id)

    def list_all(self) -> list[Todo]:
        return list(self._todos.values())

    def update(self, todo: Todo) -> Todo:
        self._todos[todo.id] = todo
        return todo

    def delete(self, todo_id: int) -> bool:
        if todo_id in self._todos:
            del self._todos[todo_id]
            return True
        return False
