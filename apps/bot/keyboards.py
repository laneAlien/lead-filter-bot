from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def yes_no_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да", callback_data="start_yes"),
                InlineKeyboardButton(text="Нет", callback_data="start_no"),
            ]
        ]
    )
