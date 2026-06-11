"""Signal generation and invalidation."""

from .builder import build_signal
from .invalidation import is_invalidated

__all__ = ["build_signal", "is_invalidated"]
