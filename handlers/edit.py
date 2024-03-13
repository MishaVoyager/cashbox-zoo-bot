import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove

from helpers import db, tg, checker, chat
from models import Resource, Record

SKIP_BTN = "Пропустить"
CONFIRM_BTN = "Подтвердить"
RETURN_BTN = "Вернуться к редактированию"
CONFIRM_OR_RETURN_KEYBOARD = tg.get_reply_keyboard([CONFIRM_BTN, RETURN_BTN])
SKIP_OR_RETURN_KEYBOARD = tg.get_reply_keyboard([SKIP_BTN, RETURN_BTN])
CHOOSE_CONFIRM_OR_RETURN_MSG = f"Выберите, {CONFIRM_BTN} или {RETURN_BTN}"


class EditFSM(StatesGroup):
    choosing = State()
    editing = State()
    confirm_free_resource = State()
    confirm_delete = State()
    choose_email = State()
    choose_address = State()
    choose_return_date = State()
    choose_id = State()
    confirm_take_resource = State()


router = Router()


def buttons_for_edit(resource_is_free) -> list[str]:
    buttons = ["Дата регистрации", "Прошивка", "Комментарий"]
    if resource_is_free:
        buttons += ["Записать на пользователя", "Удалить"]
    else:
        buttons += ["Списать с пользователя"]
    buttons += ["Завершить редактирование"]
    return buttons


async def escape_editing(message: Message, state: FSMContext):
    data = await state.get_data()
    note = ""
    if "resource_id" in data.keys():
        resource_id = data["resource_id"]
        resource = await Resource.get_single(resource_id)
        note = await db.format_note(resource, message.chat.id)
    await state.clear()
    await message.answer(
        text=f"Вы завершили редактирование\r\n\r\n{note}",
        reply_markup=ReplyKeyboardRemove()
    )

@router.message(F.text.lower().startswith("завершить"))
async def stop_editing_handler(message: Message, state: FSMContext):
    await escape_editing(message, state)


@router.message(F.text.lower().startswith("вернуться"))
async def cancel_handler(message: Message, state: FSMContext):
    resource_id = (await state.get_data())["resource_id"]
    resource = await Resource.get_single(resource_id)
    await state.set_state(EditFSM.choosing)
    note = await db.format_note(resource, message.chat.id)
    await message.answer(
        text=f"Вы вернулись к редактированию\r\n\r\n{note}",
        reply_markup=tg.get_reply_keyboard(buttons_for_edit(not resource.user_email))
    )


@router.message(F.text.regexp(r"\/edit.+"))
async def edit_resource_handler(message: Message, state: FSMContext):
    if not await checker.is_admin(message.chat.id):
        await message.answer(chat.not_admin_error_msg)
        return
    resource_id = int(message.text.removeprefix("/edit"))
    resource = await Resource.get_single(resource_id)
    buttons = buttons_for_edit(not resource.user_email)
    await state.set_state(EditFSM.choosing)
    await state.update_data(resource_id=resource_id)
    await message.answer(
        text="Выберите действие",
        reply_markup=tg.get_reply_keyboard(buttons)
    )


@router.message(EditFSM.choosing)
async def choosing_handler(message: Message, state: FSMContext):
    field_name = ""
    match message.text:
        case "Комментарий":
            field_name = db.get_field_name(Resource.comment)
        case "Дата регистрации":
            field_name = db.get_field_name(Resource.reg_date)
        case "Прошивка":
            field_name = db.get_field_name(Resource.firmware)
        case "Списать с пользователя":
            await state.set_state(EditFSM.confirm_free_resource)
            await message.answer(
                text="Точно хотите списать устройство с пользователя?",
                reply_markup=CONFIRM_OR_RETURN_KEYBOARD
            )
            return
        case "Удалить":
            await state.set_state(EditFSM.confirm_delete)
            await message.answer(
                text="Точно хотите удалить устройство?",
                reply_markup=CONFIRM_OR_RETURN_KEYBOARD
            )
            return
        case "Записать на пользователя":
            await state.set_state(EditFSM.choose_email)
            await message.answer(
                text=chat.ask_email_msg,
                reply_markup=ReplyKeyboardRemove()
            )
            return
        case _:
            await escape_editing(message, state)
            return
    await state.update_data(field_name=field_name)
    await state.set_state(EditFSM.editing)
    await message.answer(
        text="Введите значение",
        reply_markup=tg.get_reply_keyboard(["Очистить поле"])
    )


@router.message(EditFSM.editing)
async def editing_handler(message: Message, state: FSMContext):
    value = message.text.strip()
    field_name = (await state.get_data())["field_name"]
    if value == "Очистить поле":
        value = None
    if field_name == db.get_field_name(Resource.reg_date) and value:
        value = checker.try_convert_to_ddmmyyyy(value)
        if not value:
            await message.answer(checker.ResourceError.WRONG_DATE.value)
            return
    resource_id = (await state.get_data())["resource_id"]
    resource = await Resource.update(resource_id, **{field_name: value})
    logging.info(
        f"Пользователь{chat.get_username_str(message)}с chat_id {message.chat.id} отредактировал "
        f"поле {field_name} для ресурса {repr(resource)}")
    await state.set_state(EditFSM.choosing)
    await message.answer(
        text=chat.edit_success_msg,
        reply_markup=tg.get_reply_keyboard(buttons_for_edit(not resource.user_email))
    )


@router.message(EditFSM.confirm_free_resource)
async def confirm_free_handler(message: Message, state: FSMContext):
    text = message.text.strip()
    resource_id = (await state.get_data())["resource_id"]
    if text == CONFIRM_BTN:
        resource = await Resource.get_single(resource_id)
        await db.return_resource(resource_id)
        logging.info(
            f"Админ{chat.get_username_str(message)}с chat_id {message.chat.id} списал "
            f"с пользователя устройство {repr(resource)}")
        await db.notify_user_about_returning(message, resource.user_email, resource)
        next_user_email = await db.pass_resource_to_next_user(resource_id)
        if next_user_email:
            await db.notify_next_user_about_taking(message, next_user_email, resource)
        await state.set_state(EditFSM.choosing)
        await message.answer(
            text=chat.get_take_from_user_msg(resource.user_email, resource),
            reply_markup=tg.get_reply_keyboard(buttons_for_edit(True))
        )
    else:
        await message.answer(CHOOSE_CONFIRM_OR_RETURN_MSG)


@router.message(EditFSM.confirm_delete)
async def confirm_delete_handler(message: Message, state: FSMContext):
    text = message.text.strip()
    resource_id = (await state.get_data())["resource_id"]
    if text == CONFIRM_BTN:
        resource: Resource = await Resource.get_single(resource_id)
        if resource.user_email:
            await message.answer(
                text=chat.delete_taken_error_msg,
                reply_markup=ReplyKeyboardRemove()
            )
            await state.clear()
            return
        await Resource.delete(resource_id)
        logging.info(
            f"Админ{chat.get_username_str(message)}с chat_id {message.chat.id} удалил "
            f"устройство {repr(resource)}")
        await state.clear()
        await message.answer(
            text=chat.delete_success_msg,
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await message.answer(CHOOSE_CONFIRM_OR_RETURN_MSG)


@router.message(EditFSM.choose_email)
async def choose_email_handler(message: Message, state: FSMContext):
    user_email = message.text.strip()
    if not checker.is_kontur_email(user_email):
        await message.answer(checker.ResourceError.WRONG_EMAIL.value)
        return
    await state.update_data(**{db.get_field_name(Resource.user_email): user_email})
    await state.set_state(EditFSM.choose_address)
    await message.answer(
        text=chat.ask_address_msg,
        reply_markup=SKIP_OR_RETURN_KEYBOARD
    )


@router.message(EditFSM.choose_address)
async def add_address(message: Message, state: FSMContext):
    address = message.text.strip()
    if SKIP_BTN in address:
        address = None
    await state.update_data(**{db.get_field_name(Resource.address): address})
    await state.set_state(EditFSM.choose_return_date)
    await message.answer(
        text=chat.ask_return_date_msg,
        reply_markup=SKIP_OR_RETURN_KEYBOARD
    )


@router.message(EditFSM.choose_return_date)
async def add_return_date(message: Message, state: FSMContext):
    return_date = message.text.strip()
    if SKIP_BTN in return_date:
        return_date = None
    else:
        return_date = checker.try_convert_to_ddmmyyyy(return_date)
        if not return_date:
            await message.answer(checker.ResourceError.WRONG_DATE.value)
            return
        if checker.is_paste_date(return_date):
            await message.answer(chat.pass_date_error_msg)
            return
    await state.update_data(**{db.get_field_name(Resource.return_date): return_date})
    await state.set_state(EditFSM.confirm_take_resource)
    await message.answer(
        text="Подтвердите запись устройства на пользователя",
        reply_markup=CONFIRM_OR_RETURN_KEYBOARD
    )


@router.message(EditFSM.confirm_take_resource)
async def finish_adding_resource(message: Message, state: FSMContext):
    command = message.text.strip()
    if command != CONFIRM_BTN:
        await message.answer(CHOOSE_CONFIRM_OR_RETURN_MSG)
        return
    data = await state.get_data()
    resource: Resource = await Resource.take(
        resource_id=data["resource_id"], user_email=data["user_email"],
        address=data["address"],
        return_date=data["return_date"])
    await Record.add(data["resource_id"], data["user_email"], db.ActionType.TAKE)
    await state.set_state(EditFSM.choosing)
    await message.answer(
        text=chat.get_pass_to_user_msg(resource),
        reply_markup=tg.get_reply_keyboard(buttons_for_edit(False))
    )
    await db.notify_user_about_taking(message, data['user_email'], resource)
    logging.info(
        f"Админ{chat.get_username_str(message)}с chat_id {message.chat.id} записал "
        f"на пользователя устройство: {repr(resource)}")
