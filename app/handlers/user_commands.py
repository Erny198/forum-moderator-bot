from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.keyboards.inline import commitment_action_keyboard
from app.services.commitment_service import get_active_commitments_for_user
from app.services.user_service import get_or_create_user

logger = logging.getLogger(__name__)
router = Router(name="user_commands")


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    # Only handle in private chats
    if message.chat.type != "private":
        return

    try:
        await get_or_create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
    except Exception as exc:
        logger.error("Failed to upsert user on /start: %s", exc)

    first_name = message.from_user.first_name or "участник"
    await message.answer(
        f"Привет, {first_name}! 👋\n\n"
        "Я помогаю участникам Форум-группы фиксировать и отслеживать обещания.\n\n"
        "Когда ты пишешь обещание в группе, я предлагаю его зафиксировать, "
        "а потом напоминаю о нём в еженедельных сообщениях.\n\n"
        "Доступные команды:\n"
        "/my_promises — посмотреть активные обещания\n"
        "/done — отметить обещание как выполненное\n"
        "/cancel — отменить обещание\n"
        "/help — помощь\n"
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    if message.chat.type != "private":
        return

    await message.answer(
        "📋 Доступные команды:\n\n"
        "/my_promises — посмотреть все активные обещания\n"
        "/done — отметить обещание как выполненное\n"
        "/cancel — отменить обещание\n"
        "/start — приветственное сообщение\n"
        "/help — это сообщение\n\n"
        "Как работает бот:\n"
        "1. Ты пишешь в группе обещание (например, «До пятницы отправлю документ»)\n"
        "2. Бот предлагает его зафиксировать\n"
        "3. Ты подтверждаешь, редактируешь или отклоняешь\n"
        "4. Каждую неделю бот напоминает о активных обещаниях\n"
    )


@router.message(Command("my_promises"))
async def cmd_my_promises(message: Message) -> None:
    if message.chat.type != "private":
        return

    try:
        commitments = await get_active_commitments_for_user(message.from_user.id)
    except Exception as exc:
        logger.error("Failed to get commitments for user %d: %s", message.from_user.id, exc)
        await message.answer("Произошла ошибка при получении обещаний. Попробуйте позже.")
        return

    if not commitments:
        await message.answer("У тебя нет активных обещаний. 🎉")
        return

    await message.answer(f"📋 Твои активные обещания ({len(commitments)}):")
    for c in commitments:
        deadline_part = f"\n⏰ Дедлайн: {c.deadline_text}" if c.deadline_text else ""
        await message.answer(
            f"📌 {c.commitment_text}{deadline_part}",
            reply_markup=commitment_action_keyboard(c.id),
        )


@router.message(Command("done"))
async def cmd_done(message: Message) -> None:
    if message.chat.type != "private":
        return

    try:
        commitments = await get_active_commitments_for_user(message.from_user.id)
    except Exception as exc:
        logger.error("Failed to get commitments for /done: %s", exc)
        await message.answer("Произошла ошибка. Попробуйте позже.")
        return

    if not commitments:
        await message.answer("У тебя нет активных обещаний.")
        return

    await message.answer("Выбери выполненное обещание:")
    for c in commitments:
        await message.answer(
            f"📌 {c.commitment_text}",
            reply_markup=commitment_action_keyboard(c.id),
        )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message) -> None:
    if message.chat.type != "private":
        return

    try:
        commitments = await get_active_commitments_for_user(message.from_user.id)
    except Exception as exc:
        logger.error("Failed to get commitments for /cancel: %s", exc)
        await message.answer("Произошла ошибка. Попробуйте позже.")
        return

    if not commitments:
        await message.answer("У тебя нет активных обещаний.")
        return

    await message.answer("Выбери обещание для отмены:")
    for c in commitments:
        await message.answer(
            f"📌 {c.commitment_text}",
            reply_markup=commitment_action_keyboard(c.id),
        )
