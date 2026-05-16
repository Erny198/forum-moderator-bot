from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def commitment_proposal_keyboard(message_id: int) -> InlineKeyboardMarkup:
    """Keyboard shown when bot proposes to save a commitment in group chat."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Зафиксировать",
            callback_data=f"commitment:confirm:{message_id}",
        ),
        InlineKeyboardButton(
            text="✏️ Изменить",
            callback_data=f"commitment:edit:{message_id}",
        ),
        InlineKeyboardButton(
            text="❌ Не фиксировать",
            callback_data=f"commitment:reject:{message_id}",
        ),
    )
    return builder.as_markup()


def commitment_action_keyboard(commitment_id: int) -> InlineKeyboardMarkup:
    """Keyboard for managing a saved commitment (done / cancel)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Выполнено",
            callback_data=f"commitment:done:{commitment_id}",
        ),
        InlineKeyboardButton(
            text="❌ Отменить",
            callback_data=f"commitment:cancel:{commitment_id}",
        ),
    )
    return builder.as_markup()


def commitment_reminder_keyboard(commitment_id: int) -> InlineKeyboardMarkup:
    """Keyboard used in weekly reminder messages."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Выполнено",
            callback_data=f"commitment:done:{commitment_id}",
        ),
        InlineKeyboardButton(
            text="⏳ В работе",
            callback_data=f"commitment:active:{commitment_id}",
        ),
        InlineKeyboardButton(
            text="❌ Отменить",
            callback_data=f"commitment:cancel:{commitment_id}",
        ),
    )
    return builder.as_markup()
