"""Logging utility — orphan, nothing imports this."""


class Logger:
    def info(self, msg: str) -> None:
        print(f"INFO: {msg}")

    def error(self, msg: str) -> None:
        print(f"ERROR: {msg}")
