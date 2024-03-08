import logging
from re import Match

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove

from helpers import db, chat, tg
from models import Resource, User, Record, ActionType

router = Router()


class ActionsFSM(StatesGroup):
    confirm = State()


@router.message(F.text.regexp(r"^(\/return|\/queue|\/leave)(\d+)$").as_("match"))
async def actions_handler(message: Message, match: Match[str], state: FSMContext):
    action = match.group(1)
    resource_id = int(match.group(2))
    await message.answer(
        text="Вы уверены?",
        reply_markup=tg.get_reply_keyboard(["Подтвердить", "Отменить"]))
    await state.set_state(ActionsFSM.confirm)
    await state.set_data({"action": action, "resource_id": resource_id})


@router.message(ActionsFSM.confirm)
async def confirm_handler(message: Message, state: FSMContext):
    if message.text.strip() != "Подтвердить":
        await message.answer("Выберите, подтвердить или отменить")
        return
    data = await state.get_data()
    resource_id = data["resource_id"]
    action = data["action"]
    reply = ""
    match (action):
        case "/return":
            reply = await return_resource(message, resource_id)
        case "/queue":
            reply = await queue_resource(message, resource_id)
        case "/leave":
            reply = await leave_resource(message, resource_id)
    await message.answer(text=reply, reply_markup=ReplyKeyboardRemove())
    await state.clear()


async def return_resource(message: Message, resource_id: int) -> str:
    resources = await Resource.get_by_primary(resource_id)
    username = chat.get_username_str(message)
    if len(resources) == 0:
        logging.error(
            f"Пользователь{username}с chat_id{message.chat.id} пытался вернуть "
            f"устройство с resource_id {resource_id}, но оно не нашлось")
        return chat.unexpected_resource_not_found_error_msg
    resource: Resource = resources[0]
    user = await User.get_current(message.chat.id)
    if resource.user_email != user.email:
        logging.error(f"Пользователь {repr(user)} пытался вернуть устройство, "
                      f"записанное на другого пользователя: {repr(resource)}")
        return chat.return_others_device_msg
    await db.return_resource(resource_id)
    next_user_email = await db.pass_resource_to_next_user(resource_id)
    if next_user_email:
        await db.notify_next_user_about_taking(message, next_user_email, resource)
    logging.info(f"Пользователь {repr(user)} вернул устройство {repr(resource)}")
    return f"Списали с вас устройство {resource.name}."


async def queue_resource(message: Message, resource_id: int) -> str:
    resource = (await Resource.get_by_primary(resource_id))[0]
    user = await User.get_current(message.chat.id)
    records = await db.get_resource_queue(resource_id)
    if user.email in [record.user_email for record in records]:
        return chat.queue_second_time_error_msg
    await Record.add(resource_id=resource.id, email=user.email, action=ActionType.QUEUE)
    logging.info(f"Пользователь {repr(user)} встал в очередь на устройство {repr(resource)}")
    return f"Добавили вас в очередь на устройство {resource.name}"


async def leave_resource(message: Message, resource_id: int) -> str:
    resource = (await Resource.get_by_primary(resource_id))[0]
    user = await User.get_current(message.chat.id)
    records = await db.get_resource_queue(resource_id)
    if user.email not in [record.user_email for record in records]:
        logging.info(f"Пользователь {repr(user)} пытался дважды покинуть очередь на устройство {repr(resource)}")
        return chat.leave_left_error_msg
    result = await Record.delete(**{
        db.get_field_name(Record.resource): resource_id,
        db.get_field_name(Record.action): ActionType.QUEUE,
        db.get_field_name(Record.user_email): user.email})
    if result:
        logging.info(f"Пользователь {repr(user)} покинул очередь на устройство {repr(resource)}")
        return "Вы покинули очередь за устройством"
    else:
        logging.error(f"Пользователь {repr(user)} не смог покинуть очередь "
                      f"на устройство {repr(resource)} из-за ошибки удаления Record")
        return chat.leaving_queue_error_msg
