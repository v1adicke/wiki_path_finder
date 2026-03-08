from __future__ import annotations

from typing import Optional, Tuple
from search.api_client import WikiApiClient

FORBIDDEN_CHARS = set("#<>[]{}|")


def normalize_title(title: str) -> str:
    """Приводит ввод к аккуратному виду для дальнейшей проверки"""
    t = (title or "").strip().replace("_", " ")
    return " ".join(t.split())


def validate_title_syntax(title: str) -> Optional[str]:
    """Проверяет базовые правила названия и возвращает текст ошибки или None"""
    if not title:
        return "Название страницы не должно быть пустым."
    if len(title) > 255:
        return "Название страницы слишком длинное (более 255 символов)."
    if any(ch in FORBIDDEN_CHARS for ch in title):
        return "В названии есть недопустимые символы: #, <, >, [, ], {, }, |."
    if any(ord(ch) < 32 for ch in title):
        return "В названии есть управляющие символы."
    return None


async def validate_page(title: str) -> Tuple[bool, str]:
    norm = normalize_title(title)

    syntax_error = validate_title_syntax(norm)
    if syntax_error:
        return False, syntax_error

    async with WikiApiClient() as client:
        if not await client.page_exists(norm):
            return False, f"Страница «{norm}» не найдена в Википедии."

    return True, norm