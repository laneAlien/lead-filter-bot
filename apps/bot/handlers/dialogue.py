import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.bot.states import QualificationFSM
from core.llm import LLMClient
from core.schemas import NextStep
from core.services.conversation import (
    add_message,
    finalize_conversation,
    generate_verdict,
    get_or_create_user,
    start_conversation,
)

logger = logging.getLogger(__name__)

router = Router()

GREETING = (
    "Привет! Я квалифицирую заявки в digital-агентство. "
    "Задам несколько коротких вопросов про вашу задачу, это займёт 2-3 минуты."
)

Q1_BUDGET = "Какой ориентировочный бюджет на маркетинг в месяц (в рублях)? Можно диапазоном."
Q2_SERVICE = (
    "Что вас интересует — SMM, контекстная реклама, таргет, SEO или комплексное продвижение?"
)
Q3_STAGE = (
    "На каком этапе ваш бизнес — стартап без устойчивых продаж, работающий "
    "бизнес с выручкой, или крупная компания?"
)
Q4_URGENCY = "Когда планируете начать — немедленно, в течение месяца, или это план на будущее?"
Q5_EXPERIENCE = (
    "Был ли у вас опыт работы с диджитал-агентствами раньше? Если да — "
    "положительный или негативный?"
)


@router.callback_query(QualificationFSM.waiting_for_start_confirm)
async def handle_start_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if callback.data == "start_yes":
        if not isinstance(callback.message, Message) or callback.from_user is None:
            await callback.answer()
            return

        async with session_factory() as session:
            user = await get_or_create_user(
                session,
                telegram_id=callback.from_user.id,
                username=callback.from_user.username,
            )
            conv = await start_conversation(session, user)
            await add_message(session, conv.id, "assistant", GREETING)

        await state.update_data(conversation_id=conv.id)
        await state.set_state(QualificationFSM.waiting_for_budget)
        await callback.message.answer(Q1_BUDGET)
    else:
        await state.clear()
        if isinstance(callback.message, Message):
            await callback.message.answer("Хорошо, обращайтесь когда будете готовы.")

    await callback.answer()


@router.message(QualificationFSM.waiting_for_budget)
async def handle_budget(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
    llm: LLMClient,
) -> None:
    data = await state.get_data()
    conv_id: int = data["conversation_id"]

    async with session_factory() as session:
        await add_message(session, conv_id, "user", message.text or "")
        await add_message(session, conv_id, "assistant", Q2_SERVICE)

    await state.update_data(budget=message.text)
    await state.set_state(QualificationFSM.waiting_for_service_type)
    await message.answer(Q2_SERVICE)


@router.message(QualificationFSM.waiting_for_service_type)
async def handle_service_type(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
    llm: LLMClient,
) -> None:
    data = await state.get_data()
    conv_id: int = data["conversation_id"]

    async with session_factory() as session:
        await add_message(session, conv_id, "user", message.text or "")
        await add_message(session, conv_id, "assistant", Q3_STAGE)

    await state.update_data(service=message.text)
    await state.set_state(QualificationFSM.waiting_for_business_stage)
    await message.answer(Q3_STAGE)


@router.message(QualificationFSM.waiting_for_business_stage)
async def handle_business_stage(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
    llm: LLMClient,
) -> None:
    data = await state.get_data()
    conv_id: int = data["conversation_id"]

    async with session_factory() as session:
        await add_message(session, conv_id, "user", message.text or "")
        await add_message(session, conv_id, "assistant", Q4_URGENCY)

    await state.update_data(stage=message.text)
    await state.set_state(QualificationFSM.waiting_for_urgency)
    await message.answer(Q4_URGENCY)


@router.message(QualificationFSM.waiting_for_urgency)
async def handle_urgency(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
    llm: LLMClient,
) -> None:
    data = await state.get_data()
    conv_id: int = data["conversation_id"]

    async with session_factory() as session:
        await add_message(session, conv_id, "user", message.text or "")
        await add_message(session, conv_id, "assistant", Q5_EXPERIENCE)

    await state.update_data(urgency=message.text)
    await state.set_state(QualificationFSM.waiting_for_agency_experience)
    await message.answer(Q5_EXPERIENCE)


@router.message(QualificationFSM.waiting_for_agency_experience)
async def handle_agency_experience(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
    llm: LLMClient,
) -> None:
    data = await state.get_data()
    conv_id: int = data["conversation_id"]
    budget: str = data.get("budget", "не указано")
    service: str = data.get("service", "не указано")
    stage: str = data.get("stage", "не указано")
    urgency: str = data.get("urgency", "не указано")

    async with session_factory() as session:
        await add_message(session, conv_id, "user", message.text or "")

    await state.set_state(QualificationFSM.generating_verdict)
    await message.answer("Анализирую ваши ответы, секунду...")

    dialogue_summary = (
        f"Ответы клиента на квалификационные вопросы:\n\n"
        f"1. Бюджет на месяц: {budget}\n"
        f"2. Тип услуги: {service}\n"
        f"3. Стадия бизнеса: {stage}\n"
        f"4. Срочность: {urgency}\n"
        f"5. Опыт с агентствами: {message.text}\n\n"
        f"Выдай JSON-вердикт согласно правилам в системном промпте."
    )

    verdict = await generate_verdict(llm, dialogue_summary)

    async with session_factory() as session:
        await finalize_conversation(session, conv_id, verdict)

    if verdict.qualified and verdict.next_step == NextStep.book_call:
        text = (
            "Спасибо за ответы. По параметрам подходим друг другу.\n\n"
            "Менеджер свяжется с вами в ближайший рабочий день. "
            f"ID заявки: #{conv_id}"
        )
    elif verdict.next_step == NextStep.needs_clarification:
        text = (
            "Спасибо за ответы. Менеджер свяжется с вами для уточнения деталей. "
            f"ID заявки: #{conv_id}"
        )
    else:
        text = (
            "Спасибо за время. Похоже, наш формат сейчас вам не подойдёт.\n\n"
            f"{verdict.reasoning}\n\n"
            "Если ситуация изменится — будем рады поговорить позже."
        )

    await message.answer(text)
    await state.clear()
