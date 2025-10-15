# telegram_bot/step_words.py
from __future__ import annotations

def steps_word(n: int) -> str:
    """
    Возвращает корректную форму слова 'шаг' для указанного числа.
    """
    n = abs(int(n))
    n100 = n % 100
    if 11 <= n100 <= 14:
        return "шагов"
    n10 = n % 10
    if n10 == 1:
        return "шаг"
    if 2 <= n10 <= 4:
        return "шага"
    return "шагов"


def steps_text(n: int) -> str:
    """
    Возвращает строку "<n> шаг/шага/шагов".
    """
    return f"{n} {steps_word(n)}"