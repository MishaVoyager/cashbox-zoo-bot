import csv
import logging
import os
from io import StringIO

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import BufferedInputFile
from aiogram.types import Message, FSInputFile, ReplyKeyboardRemove

import models
from helpers import chat, tg, checker
from models import Visitor

LOGS_FOLDER = os.path.join(os.curdir, "logs")
CURRENT_LOG_NAME = "cashbox_zoo.log"
LOG_PATH = os.path.join(LOGS_FOLDER, CURRENT_LOG_NAME)
CANCEL_KEYBOARD = tg.get_reply_keyboard(["Отменить"])


class BackdoorFSM(StatesGroup):
    choosing = State()
    ask_current_email = State()
    ask_new_email = State()
    confirm_updating = State()


router = Router()


def get_db_files() -> list[str]:
    files = []
    for (_, _, filenames) in os.walk(os.curdir):
        files = [name for name in filenames if ".db" in name]
    return files


def get_log_files() -> list[str]:
    files = []
    for (_, _, filenames) in os.walk(LOGS_FOLDER):
        files = [os.path.join(LOGS_FOLDER, name) for name in filenames if ".log" in name]
    return files


@router.message(Command("info"))
async def info_handler(message: Message, state: FSMContext) -> None:
    user = await Visitor.get_current(message.chat.id)
    if not user.is_admin:
        await message.answer(chat.not_found_msg)
        return
    await state.set_state(BackdoorFSM.choosing)
    await message.answer(
        text="Что хотите?",
        reply_markup=tg.get_reply_keyboard(
            ["Последний лог", "Все логи", "Устройства в csv", "Изменить почту юзера", "Выйти"])
    )


async def get_devices_csv() -> StringIO:
    resources = await models.Resource.get_all(1000)
    first_row = [
        "Айди",
        "Название",
        "Категория",
        "Артикул",
        "Дата регистрации",
        "Прошивка",
        "Комментарий",
        "Электронная почта",
        "Место устройства",
        "Дата возврата"
    ]
    text = StringIO()
    csv.writer(text).writerow(first_row)
    for resource in resources:
        resource_scv = await resource.get_csv_value()
        csv.writer(text).writerow(resource_scv)
    text.seek(0)
    return text


@router.message(BackdoorFSM.choosing)
async def choosing_handler(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if text == "Последний лог":
        await message.reply_document(FSInputFile(LOG_PATH))
    elif text == "Все логи":
        file_names = get_log_files()
        if len(file_names) == 0:
            logging.error("В папке не найдены логи!")
        for file_name in file_names:
            await message.reply_document(FSInputFile(file_name))
    elif text == "Устройства в csv":
        text_file = await get_devices_csv()
        file = text_file.read().encode(encoding="cp1251")
        input_file = BufferedInputFile(file, "devices.csv")
        await message.reply_document(input_file)
    elif text == "Изменить почту юзера":
        await state.set_state(BackdoorFSM.ask_current_email)
        await message.answer(
            text="Введите текущую почту пользователя в формате email@skbkontur.ru",
            reply_markup=CANCEL_KEYBOARD
        )
    elif text == "Выйти":
        await state.clear()
        await message.answer("Вы вышли из режима info", reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer("Выберите из списка вариантов")


@router.message(BackdoorFSM.ask_current_email)
async def ask_current_email_handler(message: Message, state: FSMContext):
    current_email = message.text.strip().lower()
    if checker.is_kontur_email(current_email) is None:
        await message.answer(
            text=checker.ResourceError.WRONG_EMAIL.value,
            reply_markup=CANCEL_KEYBOARD
        )
        return
    visitors = await Visitor.get_by_primary(current_email)
    if len(visitors) == 0:
        await message.answer(
            text="Не найден пользователь с такой почтой. Укажите другую почту",
            reply_markup=CANCEL_KEYBOARD
        )
        return
    await state.update_data(current_email=current_email)
    await state.set_state(BackdoorFSM.ask_new_email)
    await message.answer(
        text="На какую почту хотите ее заменить? Тоже в формате email@skbkontur.ru",
        reply_markup=CANCEL_KEYBOARD
    )


@router.message(BackdoorFSM.ask_new_email)
async def ask_new_email_handler(message: Message, state: FSMContext):
    new_email = message.text.strip().lower()
    if checker.is_kontur_email(new_email) is None:
        await message.answer(
            text=checker.ResourceError.WRONG_EMAIL.value,
            reply_markup=CANCEL_KEYBOARD
        )
        return
    visitors = await Visitor.get_by_primary(new_email)
    if len(visitors) != 0:
        await message.answer(
            text="Пользователь с такой почтой уже есть. Укажите другую почту",
            reply_markup=CANCEL_KEYBOARD
        )
        return
    await state.update_data(new_email=new_email)
    await state.set_state(BackdoorFSM.confirm_updating)
    await message.answer(
        text="Точно-точно обновляем почту пользователя?",
        reply_markup=tg.get_reply_keyboard(["Да", "Отменить"])
    )


@router.message(BackdoorFSM.confirm_updating)
async def confirm_updating_handler(message: Message, state: FSMContext):
    if message.text != "Да":
        await message.answer(
            text="Выберите, Да или Отменить",
            reply_markup=tg.get_reply_keyboard(["Да", "Отменить"])
        )
        return
    data = await state.get_data()
    current_email = data["current_email"]
    new_email = data["new_email"]
    success = await models.Visitor.update_email(current_email, new_email)
    if not success:
        await message.answer(chat.unexpected_action_msg)
        await state.clear()
        logging.error(f"При обновлении email не найден пользователь с почтой {current_email}")
    await message.answer(
        text="Вы успешно обновили почту",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()
