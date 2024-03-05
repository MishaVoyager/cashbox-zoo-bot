from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery

from helpers import db, tg, chat
from models import Resource, User

router = Router()


@router.message(Command("start"))
async def welcome_handler(message: Message, command: CommandObject):
    """Обрабатывает команду start. Если она с параметром (?start=something), то сразу ищет по ресурсам"""
    if command.args:
        resources = await Resource.search(command.args.strip())
        if len(resources) == 0:
            await message.answer(chat.not_found_msg)
        else:
            await search_resource(message, 1, resources)
        return
    await welcome(message)


@router.message(Command("help"))
async def help_handler(message: Message):
    await welcome(message)


async def welcome(message: Message):
    user: User = await User.get_current(str(message.chat.id))
    if not user.is_admin:
        await message.answer(chat.welcome_msg)
    else:
        await message.answer(chat.admin_welcome_msg)


@router.message(Command("all"))
async def show_keyboard(message: Message):
    await search_resource(message, 1)


async def search_resource(message: Message, page: int, resources: list[Resource] = None, call: CallbackQuery = None):
    if not resources:
        resources = await Resource.get_all()
    if len(resources) == 0:
        await message.answer(chat.not_found_msg)
        return
    paginator = tg.Paginator(page, resources)
    keyboard = paginator.create_keyboard("search_resource")
    notes = await db.format_notes(paginator.get_objects_on_page(), message.chat.id)
    text = paginator.result_message() + notes
    if not call:
        await message.answer(text=text, reply_markup=keyboard)
    else:
        await call.message.edit_text(text=text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("search_resource"))
async def search_callback(call: CallbackQuery):
    data = str(call.data)
    page_number = int(data.split()[1])
    await search_resource(call.message, page_number, call=call)


@router.message(Command("wishlist"))
async def wishlist_handler(message: Message):
    await get_wishlist(message, 1)


async def get_wishlist(message: Message, page: int, call: CallbackQuery | None = None):
    user = await User.get_current(str(message.chat.id))
    resources = await db.get_waited_resources_for_user(user)
    if len(resources) == 0:
        await message.answer(chat.empty_wishlist)
        return
    paginator = tg.Paginator(page, resources)
    keyboard = paginator.create_keyboard("wishlist")
    notes = await db.format_notes(paginator.get_objects_on_page(), str(message.chat.id))
    text = paginator.result_message() + notes
    if not call:
        await message.answer(text=text, reply_markup=keyboard)
    else:
        await call.message.edit_text(text=text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("wishlist"))
async def mine_callback(call: CallbackQuery):
    data = str(call.data)
    page_number = int(data.split()[1])
    await get_wishlist(call.message, page_number, call)


@router.message(Command("mine"))
async def get_mine_resources_handler(message: Message):
    await get_mine_resources(message, 1)


async def get_mine_resources(message: Message, page: int, call: CallbackQuery | None = None):
    user = await User.get_current(str(message.chat.id))
    resources = await Resource.get_resources_taken_by_user(user)
    if len(resources) == 0:
        await message.answer(chat.user_have_no_device_msg)
        return
    paginator = tg.Paginator(page, resources)
    keyboard = paginator.create_keyboard("mine")
    notes = await db.format_notes(paginator.get_objects_on_page(), str(message.chat.id))
    text = paginator.result_message() + notes
    if not call:
        await message.answer(text=text, reply_markup=keyboard)
    else:
        await call.message.edit_text(text=text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("mine"))
async def mine_callback(call: CallbackQuery):
    data = str(call.data)
    page_number = int(data.split()[1])
    await get_mine_resources(call.message, page_number, call)


@router.message(Command("categories"))
async def get_categories_handler(message: Message):
    active_categories = await Resource.get_categories()
    if len(active_categories) == 0:
        await message.answer("Не найдена ни одна категория")
        return
    await message.answer(
        text=chat.ask_category_msg,
        reply_markup=tg.get_inline_keyboard(active_categories, "categories"))


@router.callback_query(F.data.startswith("categories"))
async def category_callback(call: CallbackQuery):
    category = str(call.data).split()[1]
    resources = await Resource.get({"category_name": category})
    await call.answer()
    await search_resource(call.message, 1, resources)


@router.message(F.text)
async def message_reply(message: Message):
    text = message.text.strip()
    if text is None or text == "":
        await welcome_handler(message)
    else:
        resources = await Resource.search(text)
        if len(resources) == 0:
            await message.answer(chat.not_found_msg)
        else:
            await search_resource(message, 1, resources)
