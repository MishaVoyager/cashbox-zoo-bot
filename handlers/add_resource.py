import csv
import logging
from typing import BinaryIO
from io import StringIO

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove
from charset_normalizer import from_bytes

from helpers import checker, db, tg, chat
from models import Resource, Visitor, Category

CANCEL_BTN = "Галя, отмена"
SKIP_BTN = "Пропустить"
ADD_BTN = "Добавить"
CANCEL_KEYBOARD = tg.get_reply_keyboard([CANCEL_BTN])
SKIP_OR_CANCEL_KEYBOARD = tg.get_reply_keyboard([SKIP_BTN, CANCEL_BTN])
ADD_OR_CANCEL_KEYBOARD = tg.get_reply_keyboard([ADD_BTN, CANCEL_BTN])


class AddResourceFSM(StatesGroup):
    choosing = State()
    uploading = State()
    write_id = State()
    write_vendor_code = State()
    write_name = State()
    write_category = State()
    write_reg_date = State()
    write_firmware = State()
    write_comment = State()
    write_user_email = State()
    write_address = State()
    write_return_date = State()
    finish = State()


router = Router()


@router.message(Command("add"))
async def add_resource_command(message: Message, state: FSMContext):
    user = await Visitor.get_current(message.chat.id)
    if not user.is_admin:
        await message.answer(chat.not_found_msg)
        return
    await state.set_state(AddResourceFSM.choosing)
    await message.answer(
        text="Хотите добавить устройства по одному или загрузить файл?",
        reply_markup=tg.get_reply_keyboard(["По одному", "Файлом"])
    )


@router.message(AddResourceFSM.choosing)
async def add_one_by_one_handler(message: Message, state: FSMContext):
    text = message.text.strip()
    if text == "По одному":
        await state.set_state(AddResourceFSM.write_id)
        await state.set_data(Resource.get_fields())
        await message.answer(text=chat.ask_id, reply_markup=CANCEL_KEYBOARD)
    elif text == "Файлом":
        await state.set_state(AddResourceFSM.uploading)
        await message.answer(text=chat.ask_file_msg, reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer(chat.ask_way_of_adding_msg)

@router.message(AddResourceFSM.write_id)
async def add_id(message: Message, state: FSMContext):
    if not message.text.strip().isnumeric():
        await message.answer(f"{checker.ResourceError.WRONG_ID.value}. Пожалуйста, введите число")
        return
    resource_id = int(message.text.strip())
    existed_resources: list[Resource] = await Resource.get_by_primary(resource_id)
    if len(existed_resources) >= 1:
        await state.clear()
        await message.answer(
            text=f"Уже есть устройства с таким id. Отредактировать их можно командой "
                 f"edit\r\n\r\n{await db.format_notes(existed_resources, message.chat.id)}",
            reply_markup=ReplyKeyboardRemove())
        return
    await state.update_data({db.get_field_name(Resource.id): resource_id})
    await state.set_state(AddResourceFSM.write_vendor_code)
    await message.answer(
        text=chat.ask_vendor_code_msg,
        reply_markup=CANCEL_KEYBOARD
    )


@router.message(AddResourceFSM.write_vendor_code)
async def add_vendor_code(message: Message, state: FSMContext):
    vendor_code = message.text.strip()
    existed_resources: list[Resource] = await Resource.get_by_vendor_code(vendor_code)
    if len(existed_resources) >= 1:
        await state.clear()
        await message.answer(
            text=f"Уже есть устройства с таким артикулом. Отредактировать их можно командой "
                 f"edit\r\n\r\n{await db.format_notes(existed_resources, message.chat.id)}",
            reply_markup=ReplyKeyboardRemove())
        return
    await state.update_data({db.get_field_name(Resource.vendor_code): vendor_code})
    await state.set_state(AddResourceFSM.write_name)
    await message.answer(
        text=chat.ask_name_msg,
        reply_markup=CANCEL_KEYBOARD
    )


@router.message(AddResourceFSM.write_name)
async def add_name(message: Message, state: FSMContext):
    await state.update_data(**{db.get_field_name(Resource.name): message.text.strip()})
    available_categories = [i.name for i in (await Category.get_all())]
    await state.set_state(AddResourceFSM.write_category)
    await message.answer(
        text=chat.ask_category_msg,
        reply_markup=tg.get_reply_keyboard(available_categories + [CANCEL_BTN])
    )


@router.message(AddResourceFSM.write_category)
async def add_category(message: Message, state: FSMContext):
    category = message.text.strip()
    if not await checker.is_right_category(category):
        await message.answer(f"{checker.ResourceError.WRONG_CATEGORY.value}. Выберите один из вариантов")
        return
    await state.update_data(**{db.get_field_name(Resource.category_name): category})
    await state.set_state(AddResourceFSM.write_reg_date)
    await message.answer(
        text=chat.ask_reg_date_msg,
        reply_markup=SKIP_OR_CANCEL_KEYBOARD
    )


@router.message(AddResourceFSM.write_reg_date)
async def add_reg_date(message: Message, state: FSMContext):
    reg_date = message.text.strip()
    if SKIP_BTN in reg_date:
        reg_date = None
    else:
        reg_date = checker.try_convert_to_ddmmyyyy(reg_date)
        if not reg_date:
            await message.answer(checker.ResourceError.WRONG_DATE.value)
            return
    await state.update_data(**{db.get_field_name(Resource.reg_date): reg_date})
    await state.set_state(AddResourceFSM.write_firmware)
    await message.answer(
        text=chat.ask_firmware_msg,
        reply_markup=SKIP_OR_CANCEL_KEYBOARD
    )


@router.message(AddResourceFSM.write_firmware)
async def add_firmware(message: Message, state: FSMContext):
    firmware = message.text.strip()
    if SKIP_BTN in firmware:
        firmware = None
    await state.update_data(**{db.get_field_name(Resource.firmware): firmware})
    await state.set_state(AddResourceFSM.write_comment)
    await message.answer(
        text=chat.ask_comment_msg,
        reply_markup=SKIP_OR_CANCEL_KEYBOARD
    )


@router.message(AddResourceFSM.write_comment)
async def add_comment(message: Message, state: FSMContext):
    comment = message.text.strip()
    if SKIP_BTN in comment:
        comment = None
    await state.update_data(**{db.get_field_name(Resource.comment): comment})
    await state.set_state(AddResourceFSM.write_user_email)
    await message.answer(
        text=chat.ask_email_msg,
        reply_markup=SKIP_OR_CANCEL_KEYBOARD
    )


@router.message(AddResourceFSM.write_user_email)
async def add_user_email(message: Message, state: FSMContext):
    user_email = message.text.strip()
    if SKIP_BTN in user_email:
        await state.set_state(AddResourceFSM.finish)
        await message.answer(
            text=chat.confirm_adding_msg,
            reply_markup=ADD_OR_CANCEL_KEYBOARD
        )
        return
    else:
        if not checker.is_kontur_email(user_email):
            await message.answer(checker.ResourceError.WRONG_EMAIL.value)
            return
    await state.update_data(**{db.get_field_name(Resource.user_email): user_email})
    await state.set_state(AddResourceFSM.write_address)
    await message.answer(
        text=chat.ask_address_msg,
        reply_markup=SKIP_OR_CANCEL_KEYBOARD
    )


@router.message(AddResourceFSM.write_address)
async def add_address(message: Message, state: FSMContext):
    address = message.text.strip()
    if SKIP_BTN in address:
        address = None
    await state.update_data(**{db.get_field_name(Resource.address): address})
    await state.set_state(AddResourceFSM.write_return_date)
    await message.answer(
        text=chat.ask_return_date_msg,
        reply_markup=SKIP_OR_CANCEL_KEYBOARD
    )


@router.message(AddResourceFSM.write_return_date)
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
    await state.set_state(AddResourceFSM.finish)
    await message.answer(
        text=chat.confirm_adding_msg,
        reply_markup=ADD_OR_CANCEL_KEYBOARD
    )


@router.message(AddResourceFSM.finish)
async def finish_adding_resource(message: Message, state: FSMContext):
    command = message.text.strip()
    if command != ADD_BTN:
        await message.answer("Выберите, отменить или добавить")
        return
    data = await state.get_data()
    fields_and_values = {k: v for k, v in data.items() if k in Resource.get_fields_names()}
    resource = await Resource.add(**fields_and_values)
    if not resource:
        await message.answer("Не удалось добавить устройство. " + chat.unexpected_action_msg)
        return
    user_name = chat.get_username_str(message)
    logging.info(
        f"Пользователь{user_name}с chat_id {message.chat.id} добавил устройство {repr(resource)}")
    await state.clear()
    await message.answer(
        text=f"Вы добавили устройство!\r\n\r\n{str(resource)}",
        reply_markup=ReplyKeyboardRemove()
    )


def get_charset(file: BinaryIO):
    charset = from_bytes(file.read()).best().encoding
    logging.info(f"Charset normalizer определил кодировку как: {charset}")
    if charset not in ["cp1251", "utf_8"]:
        charset = "cp1251"
    logging.info(f"Для декодирования выбрана кодировка: {charset}")
    file.seek(0)
    return charset


async def check_csv(in_memory_file: BinaryIO) -> tuple[dict[int, list[checker.ResourceError]], list] | None:
    errors: dict[int, list[checker.ResourceError]] = {}
    resources = []
    charset = get_charset(in_memory_file)
    s = StringIO(in_memory_file.read().decode(encoding=charset))
    try:
        for index, row in enumerate(csv.reader(s), 1):
            if row == [] or row[0].lower() == "айди":
                continue
            fields = checker.prepare_fields(row)
            resource, resource_errors = await checker.check_resource(**fields)
            if len(resource_errors) != 0:
                errors.update({index: resource_errors})
            elif resource:
                resources.append(resource)
        return errors, resources
    except Exception:
        logging.error("При парсинге файла произошла неожиданная ошибка", exc_info=True)


@router.message(AddResourceFSM.uploading, F.document)
async def paste_from_csv(message: Message, state: FSMContext):
    if not message.document.file_name.endswith(".csv"):
        await message.answer(chat.wrong_file_format_msg)
        return
    await message.answer(chat.file_is_processing_msg)
    original_file = await message.bot.get_file(message.document.file_id)
    in_memory_file = await message.bot.download(file=original_file)
    row_errors, resources = await check_csv(in_memory_file)
    if not row_errors and not resources:
        await message.answer(chat.adding_file_error_msg)
        return
    vendor_code_doubles = checker.get_vendor_code_doubles(resources)
    vendor_code_doubles_text = checker.get_doubles_text(vendor_code_doubles, "артикулов")
    resource_id_doubles = checker.get_resource_id_doubles(resources)
    resource_id_doubles_text = checker.get_doubles_text(resource_id_doubles, "айди")
    if row_errors or vendor_code_doubles or resource_id_doubles:
        row_errors_text = checker.format_errors(row_errors)
        error_reply = "Исправьте ошибки и попробуйте снова\r\n\r\n"
        await message.answer(f"{error_reply}{row_errors_text}{vendor_code_doubles_text}{resource_id_doubles_text}")
        return
    for resource in resources:
        if resource.user_email is not None:
            await Visitor.add_if_needed(resource.user_email)
        await Resource.add_existed(resource)
        user_name = chat.get_username_str(message)
        logging.info(
            f"Пользователь{user_name}с chat_id {message.chat.id} добавил устройство {repr(resource)}")
    await state.clear()
    await message.answer("Вы успешно внесли данные!", reply_markup=ReplyKeyboardRemove())


@router.message(AddResourceFSM.uploading, F.text)
async def wrong_text(message: Message, state: FSMContext):
    if message.text.casefold() == "да":
        await state.clear()
        await message.answer(text="Загрузка файла отменена", reply_markup=ReplyKeyboardRemove())
        return
    elif message.text.casefold() == "нет":
        await message.answer(text="Тогда ждем файл в формате csv", reply_markup=ReplyKeyboardRemove())
        return
    await message.answer(
        text="Вы ввели текст. Прервать процесс загрузки файла?",
        reply_markup=tg.get_reply_keyboard(["Да", "Нет"])
    )
