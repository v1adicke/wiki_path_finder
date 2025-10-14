from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

@dataclass(slots=True)
class WikiPathResult:
    """
    Результат поиска пути.

    Attributes:
        path: Путь из страниц от начала до конца.
        elapsed_time: Время поиска.
        error: Сообщение об ошибке, если она возникла.
        steps_count: Количество узлов в пути.
    """
    path: Optional[List[str]] = None
    elapsed_time: float = 0.0
    error: Optional[str] = None
    steps_count: int = 0


    @property
    def success(self) -> bool:
        """Возвращает True если ошибок не возникло."""
        return self.path is not None and self.error is None


    def format(self, time_limit: int = 30, max_len: int = 4000) -> str:
        """
        Форматирование результата.

        Args:
            time_limit: Максимальное время поиска.
            max_len: Максимальная длина вывода.

        Returns:
            Готовый вывод с путем или ошибкой.
        """
        if self.error:
            return f"❌ Ошибка: {self.error}"

        if not self.success:
            return f"❌ Путь не найден"

        prefix = (
            f"✅ Путь найден за {self.elapsed_time:.2f} сек "
            f"({self.steps_count} шагов):\n\n"
        )

        parts = self.path or []
        rendered = " → ".join(parts)
        if len(prefix + rendered) <= max_len:
            return prefix + rendered

        visible: List[str] = []
        current = len(prefix) + 50
        for i, step in enumerate(parts):
            addition = f" → {step}" if i else step
            if current + len(addition) > max_len:
                visible.append("...")
                if parts:
                    visible.append(parts[-1])
                break
            visible.append(step)
            current += len(addition)

        return prefix + " → ".join(visible)