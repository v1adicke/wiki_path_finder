from __future__ import annotations

from typing import Optional, Tuple
import aiohttp

API_URL = "https://ru.wikipedia.org/w/api.php"
USER_AGENT = "WikiPathFinder/1.0"
FORBIDDEN_CHARS = set("#<>[]{}|")


def normalize_title(title: str) -> str:
    """
    Нормализует ввод.
    """
    t = (title or "").strip().replace("_", " ")
    return " ".join(t.split())


def validate_title_syntax(title: str) -> Optional[str]:
    """
    Синтаксическая проверка названия.
    Returns:
        Текст ошибки или None, если всё ок.
    """
    if not title:
        return "Название страницы не должно быть пустым."
    if len(title) > 255:
        return "Название страницы слишком длинное (более 255 символов)."
    if any(ch in FORBIDDEN_CHARS for ch in title):
        return "В названии есть недопустимые символы: #, <, >, [, ], {, }, |."
    if any(ord(ch) < 32 for ch in title):
        return "В названии есть управляющие символы."
    return None


async def _page_exists_ru(title: str, total_timeout: int = 15) -> bool:
    """
    Проверяет существование страницы.
    """
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "info",
    }
    timeout = aiohttp.ClientTimeout(total=total_timeout)
    async with aiohttp.ClientSession(
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
    ) as session:
        async with session.get(API_URL, params=params) as resp:
            if resp.status != 200:
                return False
            data = await resp.json(content_type=None)
    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return False
    for page in pages.values():
        if "missing" in page:
            return False
    return True


async def validate_page(title: str) -> Tuple[bool, str]:
    """
    Полная проверка: синтаксис + существование.
    Returns:
        Отформатированное название или ошибка.
    """
    norm = normalize_title(title)
    err = validate_title_syntax(norm)
    if err:
        return False, err
    exists = await _page_exists_ru(norm)
    if not exists:
        return False, f"Страница «{norm}» не найдена в русской Википедии."
    return True, norm