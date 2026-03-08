from __future__ import annotations

def steps_word(n: int) -> str:
    """Подбирает правильную форму слова шаг для числа"""
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
    """Собирает строку вида число плюс корректная форма слова шаг"""
    return f"{n} {steps_word(n)}"