from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

from search.step_words import steps_text

@dataclass(slots=True)
class WikiPathResult:
    """Хранит итог поиска пути и базовые поля для вывода"""
    path: Optional[List[str]] = None
    elapsed_time: float = 0.0
    error: Optional[str] = None
    steps_count: int = 0


    @property
    def success(self) -> bool:
        """Показывает что путь найден без ошибок"""
        return self.path is not None and self.error is None


    def format(self, time_limit: int = 30, max_len: int = 4000) -> str:
        """Собирает человекочитаемый текст результата для ответа пользователю"""
        if self.error:
            return f"❌ Ошибка: {self.error}"

        if not self.success:
            return f"❌ Путь не найден"

        prefix = (
            f"✅ Путь найден за {self.elapsed_time:.2f} сек "
            f"({steps_text(self.steps_count)}):\n\n"
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