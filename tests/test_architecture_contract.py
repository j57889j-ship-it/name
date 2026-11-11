"""Static architecture contracts that can run without Telegram credentials."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_DIR = ROOT / "bot" / "handlers" / "admin"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_each_admin_router_has_admin_filters() -> None:
    modules = [p for p in ADMIN_DIR.glob("*.py") if p.name != "__init__.py"]
    assert modules
    for path in modules:
        source = _source(path)
        assert "AdminFilter" in source, f"AdminFilter missing in {path.name}"
        assert "router.callback_query.filter(AdminFilter())" in source, f"Callback filter missing in {path.name}"
        if "@router.message" in source:
            assert "router.message.filter(AdminFilter())" in source, f"Message filter missing in {path.name}"


def test_every_admin_callback_rechecks_identity() -> None:
    modules = [p for p in ADMIN_DIR.glob("*.py") if p.name != "__init__.py"]
    for path in modules:
        tree = ast.parse(_source(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            callback_handler = any(
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "callback_query"
                for decorator in node.decorator_list
            )
            if callback_handler:
                body = ast.get_source_segment(_source(path), node) or ""
                assert "admin_callback_guard" in body, f"Callback guard missing: {path.name}:{node.name}"


def test_public_menu_has_only_support_action() -> None:
    source = _source(ROOT / "bot" / "ui" / "keyboards.py")
    start = source.index("def user_home")
    end = source.index("def admin_home")
    user_menu = source[start:end]
    assert "user:contact" in user_menu
    assert "adm:" not in user_menu
    assert "ai:" not in user_menu
    assert "post:" not in user_menu


def test_no_html_tags_are_used_as_inline_keyboard_markup() -> None:
    source = _source(ROOT / "bot" / "ui" / "keyboards.py")
    assert "InlineKeyboardButton" in source
    assert "InlineKeyboardMarkup" in source
    assert "callback_data" in source
