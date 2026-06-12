"""Alert rule matching + dispatch (the buy/sell signal alerts layer)."""

from .engine import dispatch, matches, render_message

__all__ = ["matches", "dispatch", "render_message"]
