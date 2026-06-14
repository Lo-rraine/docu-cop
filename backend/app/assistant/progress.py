"""Progress tracking for agent operations (observer pattern)."""

from typing import Callable

_listeners: list[Callable[[str], None]] = []


def add_progress_listener(fn: Callable[[str], None]) -> None:
    """Register a callback to receive progress messages."""
    _listeners.append(fn)


def clear_progress_listeners() -> None:
    """Clear all registered progress listeners."""
    _listeners.clear()


def report_progress(message: str) -> None:
    """Dispatch a progress message to all registered listeners."""
    for fn in _listeners:
        fn(message)
