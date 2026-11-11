"""Shared cyber-terminal visual theme for Telegram messages."""
from __future__ import annotations

NEON = "#00FF9C"
CYAN = "#00D9FF"
PURPLE = "#B56CFF"
DARK = "#0D1117"
MUTED = "#8B949E"

BANNER = (
    "╔══════════════════════════════════╗\n"
    "║      D A S T U R L A S H  &  A I ║\n"
    "║       PRIVATE CONTROL SYSTEM     ║\n"
    "╚══════════════════════════════════╝"
)


def terminal_header(section: str = "CONTROL CENTER") -> str:
    """Return a compact, HTML-safe terminal header."""
    return f"<code>root@dasturlash:~$ {section.lower()}</code>"


def status(label: str, ok: bool = True) -> str:
    """Render a consistent terminal status tag."""
    return f"{'🟢 [ OK ]' if ok else '🔴 [ FAIL ]'} {label}"
