from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from search.api_client import WikiApiClient
from search.path_finder import WikiPathFinder
from search.result import WikiPathResult

from telegram_bot.title_validator import validate_page

router = Router()


class PathStates(StatesGroup):
    waiting_start = State()
    waiting_end = State()


async def _find_path(start_title: str, end_title: str) -> WikiPathResult:
    async with WikiApiClient() as client:
        finder = WikiPathFinder(client=client, time_limit=30)
        return await finder.find_path(start_title, end_title)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(PathStates.waiting_start)
    await message.answer(
        "Привет! Введите начальную статью Википедии (например, «Вытяжной сыр»)."
    )


@router.message(Command("info"))
async def cmd_info(message: Message) -> None:
    text = (
        "Бот ищет путь между статьями русской Википедии.\n\n"
        "1) Отправьте начальную статью.\n"
        "2) Затем отправьте конечную статью .\n"
        "3) После запуска алгоритма вы получите путь между статьями.\n"
        "Используйте кнопку «Найти ещё путь», чтобы начать заново."
    )
    await message.answer(text)


@router.message(PathStates.waiting_start, F.text)
async def got_start_article(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw:
        await message.answer("Название не должно быть пустым, введите начальную статью ещё раз.")
        return

    pending_msg = await message.answer("Проверка корректности введённой начальной статьи...")

    ok, result = await validate_page(raw)

    if not ok:
        await pending_msg.edit_text(f"❌ {result}\nПожалуйста, введите другую начальную статью.")
        return

    start_norm = result
    await pending_msg.edit_text(f"✅ Статья найдена: {start_norm}\nТеперь введите конечную статью.")

    await state.update_data(start_title=start_norm)
    await state.set_state(PathStates.waiting_end)


@router.message(PathStates.waiting_end, F.text)
async def got_end_article(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw:
        await message.answer("Название не должно быть пустым, введите конечную статью ещё раз.")
        return

    pending_msg = await message.answer("Проверка корректности введённой конечной статьи...")

    ok, result = await validate_page(raw)

    if not ok:
        await pending_msg.edit_text(f"❌ {result}\nПожалуйста, введите другую конечную статью.")
        return

    end_norm = result

    search_msg = await pending_msg.edit_text("🔎 Выполняется поиск пути между статьями...")

    data = await state.get_data()
    start_norm = data.get("start_title", "")

    find_result = await _find_path(start_norm, end_norm)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Найти ещё путь", callback_data="again")]
        ]
    )

    await state.clear()
    await search_msg.edit_text(find_result.format(), reply_markup=kb)


@router.callback_query(F.data == "again")
async def cb_again(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.answer("Введите начальную статью для нового поиска.")
    await state.set_state(PathStates.waiting_start)
    await call.answer()