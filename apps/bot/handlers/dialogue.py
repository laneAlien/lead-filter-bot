from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from apps.bot.states import QualificationFSM

router = Router()

# TODO Phase 2: implement full 5-question FSM qualification dialogue.
#
# Flow:
#   1. User confirms start (callback "start_yes") → ask budget question
#   2. Collect: budget → service_type → business_stage → urgency → agency_experience
#   3. Build message history from FSM state
#   4. Call LLMClient.chat_structured(..., QualifierVerdict) with QUALIFIER_SYSTEM_PROMPT
#   5. Save Conversation + Messages + verdict_json to DB
#   6. Send verdict summary to user


@router.callback_query(QualificationFSM.waiting_for_start_confirm)
async def handle_start_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data == "start_yes":
        await state.set_state(QualificationFSM.in_dialogue)
        if isinstance(callback.message, Message):
            await callback.message.answer(
                "Отлично. Первый вопрос: какой у вас ориентировочный бюджет на маркетинг "
                "в месяц (в рублях)?"
            )
    else:
        await state.clear()
        if isinstance(callback.message, Message):
            await callback.message.answer("Хорошо, обращайтесь когда будете готовы.")
    await callback.answer()


@router.message(QualificationFSM.in_dialogue)
async def handle_dialogue_message(message: Message, state: FSMContext) -> None:
    # TODO Phase 2: route message to LLM dialogue handler
    await message.answer("Диалог квалификации будет реализован в Фазе 2. Пока тут заглушка.")
