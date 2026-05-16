from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.services.commitment_service import (
    create_commitment,
    get_commitment_by_id,
    mark_commitment_cancelled,
    mark_commitment_done,
    update_commitment_text,
)
from app.handlers.group_messages import get_pending, remove_pending

logger = logging.getLogger(__name__)
router = Router(name="callbacks")


class EditCommitmentState(StatesGroup):
    waiting_for_text = State()


@router.callback_query(F.data.startswith("commitment:confirm:"))
async def on_commitment_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    message_id = int(callback.data.split(":")[2])
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id

    pending = get_pending(chat_id, message_id)
    if pending is None:
        await callback.message.edit_text("Это предложение уже обработано.")
        return

    # Only the original author can confirm
    if pending["telegram_user_id"] != user_id:
        await callback.answer("Только автор сообщения может подтвердить обещание.", show_alert=True)
        return

    try:
        commitment = await create_commitment(
            telegram_user_id=pending["telegram_user_id"],
            group_chat_id=pending["group_chat_id"],
            commitment_text=pending["commitment_text"],
            original_message_id=pending["original_message_id"],
            deadline_text=pending["deadline_text"],
        )
        remove_pending(chat_id, message_id)
        await callback.message.edit_text(
            f"✅ Обещание зафиксировано. Я напомню о нём в еженедельном напоминании.\n\n"
            f"«{commitment.commitment_text}»"
        )
        logger.info("Commitment confirmed: id=%d user=%d", commitment.id, user_id)
    except Exception as exc:
        logger.error("Failed to save commitment: %s", exc)
        await callback.message.edit_text("Произошла ошибка при сохранении обещания. Попробуйте позже.")


@router.callback_query(F.data.startswith("commitment:edit:"))
async def on_commitment_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    message_id = int(callback.data.split(":")[2])
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id

    pending = get_pending(chat_id, message_id)
    if pending is None:
        await callback.message.edit_text("Это предложение уже обработано.")
        return

    if pending["telegram_user_id"] != user_id:
        await callback.answer("Только автор сообщения может изменить обещание.", show_alert=True)
        return

    await state.set_state(EditCommitmentState.waiting_for_text)
    await state.update_data(
        original_message_id=message_id,
        chat_id=chat_id,
        bot_message_id=callback.message.message_id,
    )

    await callback.message.edit_text(
        "✏️ Пришли новую формулировку обещания одним сообщением."
    )


@router.message(EditCommitmentState.waiting_for_text)
async def on_edit_commitment_text(message: Message, state: FSMContext) -> None:
    new_text = message.text
    if not new_text or not new_text.strip():
        await message.reply("Пожалуйста, введи текст обещания.")
        return

    data = await state.get_data()
    original_message_id = data.get("original_message_id")
    chat_id = data.get("chat_id")

    await state.clear()

    if original_message_id is None or chat_id is None:
        await message.reply("Не удалось найти данные обещания. Попробуй снова.")
        return

    pending = get_pending(chat_id, original_message_id)
    if pending is None:
        await message.reply("Это предложение уже обработано.")
        return

    # Update text in pending
    pending["commitment_text"] = new_text.strip()

    try:
        commitment = await create_commitment(
            telegram_user_id=pending["telegram_user_id"],
            group_chat_id=pending["group_chat_id"],
            commitment_text=pending["commitment_text"],
            original_message_id=pending["original_message_id"],
            deadline_text=pending["deadline_text"],
        )
        remove_pending(chat_id, original_message_id)
        await message.reply(
            f"✅ Обещание зафиксировано с новой формулировкой. Я напомню о нём в еженедельном напоминании.\n\n"
            f"«{commitment.commitment_text}»"
        )
        logger.info("Commitment edited and saved: id=%d user=%d", commitment.id, message.from_user.id)
    except Exception as exc:
        logger.error("Failed to save edited commitment: %s", exc)
        await message.reply("Произошла ошибка при сохранении обещания. Попробуйте позже.")


@router.callback_query(F.data.startswith("commitment:reject:"))
async def on_commitment_reject(callback: CallbackQuery) -> None:
    await callback.answer()
    message_id = int(callback.data.split(":")[2])
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id

    pending = get_pending(chat_id, message_id)
    if pending is None:
        await callback.message.edit_text("Это предложение уже обработано.")
        return

    if pending["telegram_user_id"] != user_id:
        await callback.answer("Только автор сообщения может отклонить предложение.", show_alert=True)
        return

    remove_pending(chat_id, message_id)
    await callback.message.edit_text("Хорошо, не фиксирую.")
    logger.info("Commitment rejected by user=%d for message=%d", user_id, message_id)


@router.callback_query(F.data.startswith("commitment:done:"))
async def on_commitment_done(callback: CallbackQuery) -> None:
    await callback.answer()
    commitment_id = int(callback.data.split(":")[2])
    user_id = callback.from_user.id

    try:
        commitment = await get_commitment_by_id(commitment_id)
        if commitment is None:
            await callback.message.edit_text("Обещание не найдено.")
            return

        if commitment.telegram_user_id != user_id:
            await callback.answer("Это не твоё обещание.", show_alert=True)
            return

        await mark_commitment_done(commitment_id)
        await callback.message.edit_text(f"✅ Отлично, отметил как выполненное.\n\n«{commitment.commitment_text}»")
        logger.info("Commitment marked done: id=%d user=%d", commitment_id, user_id)
    except Exception as exc:
        logger.error("Failed to mark commitment done: %s", exc)
        await callback.message.edit_text("Произошла ошибка. Попробуйте позже.")


@router.callback_query(F.data.startswith("commitment:active:"))
async def on_commitment_active(callback: CallbackQuery) -> None:
    await callback.answer()
    commitment_id = int(callback.data.split(":")[2])
    user_id = callback.from_user.id

    try:
        commitment = await get_commitment_by_id(commitment_id)
        if commitment is None:
            await callback.message.edit_text("Обещание не найдено.")
            return

        if commitment.telegram_user_id != user_id:
            await callback.answer("Это не твоё обещание.", show_alert=True)
            return

        await callback.message.edit_text(f"⏳ Оставил в работе.\n\n«{commitment.commitment_text}»")
        logger.info("Commitment kept active: id=%d user=%d", commitment_id, user_id)
    except Exception as exc:
        logger.error("Failed to process active callback: %s", exc)
        await callback.message.edit_text("Произошла ошибка. Попробуйте позже.")


@router.callback_query(F.data.startswith("commitment:cancel:"))
async def on_commitment_cancel(callback: CallbackQuery) -> None:
    await callback.answer()
    commitment_id = int(callback.data.split(":")[2])
    user_id = callback.from_user.id

    try:
        commitment = await get_commitment_by_id(commitment_id)
        if commitment is None:
            await callback.message.edit_text("Обещание не найдено.")
            return

        if commitment.telegram_user_id != user_id:
            await callback.answer("Это не твоё обещание.", show_alert=True)
            return

        await mark_commitment_cancelled(commitment_id)
        await callback.message.edit_text(f"❌ Отменил это обещание.\n\n«{commitment.commitment_text}»")
        logger.info("Commitment cancelled: id=%d user=%d", commitment_id, user_id)
    except Exception as exc:
        logger.error("Failed to cancel commitment: %s", exc)
        await callback.message.edit_text("Произошла ошибка. Попробуйте позже.")
