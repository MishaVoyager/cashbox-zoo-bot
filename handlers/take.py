import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove

from helpers import checker, tg, chat
from models import Resource, User, Record, ActionType


class TakeFSM(StatesGroup):
    choosing_address = State()
    choosing_return_date = State()
    confirming = State()


router = Router()


@router.message(F.text.regexp(r"\/update_address.+"))
async def update_address_handler(message: Message, state: FSMContext):
    resource_id = int(message.text.removeprefix("/update_address"))
    await take_resource(message, state, resource_id)


@router.message(F.text.regexp(r"\/take.+"))
async def take_resource_handler(message: Message, state: FSMContext):
    resource_id = int(message.text.removeprefix("/take"))
    await take_resource(message, state, resource_id)


async def take_resource(message: Message, state: FSMContext, resource_id: int):
    resource: Resource = await Resource.get_single(resource_id)
    if not resource:
        await message.answer(chat.take_nonnexisted_error_msg)
        return
    if resource.user_email:
        await message.answer(chat.take_taken_error_msg)
        return
    await message.answer("Напишите, где будет находится устройство? Например: Офис Екб, мой стол. Или: Питер, дома")
    await state.update_data(resource_id=resource_id)
    await state.set_state(TakeFSM.choosing_address)


@router.message(TakeFSM.choosing_address)
async def enter_address(message: Message, state: FSMContext):
    address = message.text.lower().strip()
    await state.update_data(address=address)
    await state.set_state(TakeFSM.choosing_return_date)
    await message.answer(
        text="Когда вернёте? Напишите примерную дату, например, 23.11.2024",
        reply_markup=tg.get_reply_keyboard(["Пропустить"]))


@router.message(TakeFSM.choosing_return_date)
async def enter_return_date(message: Message, state: FSMContext):
    return_date = message.text.strip()
    if return_date == "Пропустить":
        return_date = None
    else:
        return_date = checker.try_convert_to_ddmmyyyy(return_date)
        if not return_date:
            await message.answer(checker.ResourceError.WRONG_DATE.value)
            return
        if checker.is_paste_date(return_date):
            await message.answer(chat.pass_date_error_msg)
            return
    await state.update_data(return_date=return_date)
    await state.set_state(TakeFSM.confirming)
    await message.answer(
        text="Записываем на вас устройство?",
        reply_markup=tg.get_reply_keyboard(["Подтвердить", "Отменить"])
    )


@router.message(TakeFSM.confirming)
async def confirm_take(message: Message, state: FSMContext):
    if message.text.lower() == "подтвердить":
        user = await User.get_current(message.chat.id)
        data = await state.get_data()
        resource_id = data["resource_id"]
        resource: Resource = await Resource.take(resource_id, user.email, data["address"], data["return_date"])
        await Record.add(resource_id, user.email, ActionType.TAKE)
        await state.clear()
        await message.answer(
            text=f"На вас записано устройство {resource.name}. Приятного пользования!",
            reply_markup=ReplyKeyboardRemove()
        )
        logging.info(f"Пользователь {repr(user)} взял устройство {repr(resource)}")
    elif message.text.lower() == "отменить":
        await state.clear()
        await message.answer(
            text="Окей, устройство не записано на вас",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await message.answer("Подтвердите или отмените запись")
