from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from apps.bot.keyboards import yes_no_keyboard
from apps.bot.states import QualificationFSM

router = Router()


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext) -> None:
    await state.set_state(QualificationFSM.waiting_for_start_confirm)
    await message.answer(
        "Привет! Я квалифицирую заявки в digital-агентство. "
        "Задам несколько коротких вопросов про вашу задачу, это займёт 2-3 минуты. "
        "Готовы начать?",
        reply_markup=yes_no_keyboard(),
    )
