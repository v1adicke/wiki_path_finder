from __future__ import annotations

import os
import sys
import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from telegram_bot.handlers import router


async def main() -> None:
    env_path = ROOT_DIR / ".env"
    load_dotenv(dotenv_path=env_path)
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Переменная окружения BOT_TOKEN не найдена")

    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_router(router)

    print("✅ Бот запущен и успешно работает", flush=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())