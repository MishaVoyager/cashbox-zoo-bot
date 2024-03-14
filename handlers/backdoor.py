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
from helpers import chat, tg
from models import Visitor

LOGS_FOLDER = os.path.join(os.curdir, "logs")
CURRENT_LOG_NAME = "cashbox_zoo.log"
LOG_PATH = os.path.join(LOGS_FOLDER, CURRENT_LOG_NAME)


class BackdoorFSM(StatesGroup):
    choosing = State()


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
        reply_markup=tg.get_reply_keyboard(["Последний лог", "Все логи", "Бэкап базы", "Устройства в csv", "Выйти"])
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
    elif text == "Бэкап базы":
        db_files = get_db_files()
        if len(db_files) == 0:
            record = "Файл базы данных не найден"
            logging.error(record)
            await message.answer(record)
            return
        elif len(db_files) > 1:
            record = "Файлов базы данных больше одного"
            logging.error(record + ''.join(db_files))
            await message.answer(record)
        await message.reply_document(FSInputFile(db_files[0]))
    elif text == "Выйти":
        await state.clear()
        await message.answer("Вы вышли из режима info", reply_markup=ReplyKeyboardRemove())
    elif text == "Устройства в csv":
        text = await get_devices_csv()
        file = text.read().encode(encoding="cp1251")
        input_file = BufferedInputFile(file, "devices.csv")
        await message.reply_document(input_file)
    else:
        await message.answer("Выберите из списка вариантов")
