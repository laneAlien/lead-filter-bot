from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from apps.bot.keyboards import yes_no_keyboard
from apps.bot.states import QualificationFSM

router = Router()

_HELP_TEXT = (
    "Контур Digital — квалификационный бот\n"
    "\n"
    "RU: Я задаю несколько вопросов о вашей задаче, чтобы менеджер подготовился к звонку. "
    "По ходу диалога можно задавать вопросы об услугах агентства — отвечу сразу.\n"
    "Начать: /start\n"
    "\n"
    "EN: I ask a few questions about your project so the manager comes prepared. "
    "Feel free to ask about our services at any point — I'll answer right away.\n"
    "Start: /start"
)


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    await message.answer(_HELP_TEXT)


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext) -> None:
    await state.set_state(QualificationFSM.waiting_for_start_confirm)
    await message.answer(
        "Привет! Я квалифицирую заявки в digital-агентство. "
        "Задам несколько коротких вопросов про вашу задачу, это займёт 2-3 минуты. "
        "Готовы начать?",
        reply_markup=yes_no_keyboard(),
    )
