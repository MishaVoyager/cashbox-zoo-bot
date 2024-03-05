from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove

from filters import not_auth
from helpers import checker, chat, tg
from models import User


class AuthFSM(StatesGroup):
    entering_email = State()
    confirming = State()


router = Router()
router.message.filter(not_auth.NotAuthFilter())


@router.message(StateFilter(None))
async def auth(message: Message, state: FSMContext):
    await message.answer(chat.not_auth_msg)
    await state.set_state(AuthFSM.entering_email)


@router.message(AuthFSM.entering_email)
async def login(message: Message, state: FSMContext):
    user_email = message.text.strip()
    if not checker.is_kontur_email(user_email):
        await message.answer(text=f"{checker.ResourceError.WRONG_EMAIL.value}\r\n{chat.wrong_email_msg}")
        return
    await state.update_data(user_email=user_email)
    await state.set_state(AuthFSM.confirming)
    await message.answer(
        text=chat.ask_confirm_auth,
        reply_markup=tg.get_reply_keyboard(["Подтвердить", "Ввести адрес заново"])
    )


@router.message(AuthFSM.confirming)
async def confirm_login(message: Message, state: FSMContext):
    text = message.text.strip()
    if text == "Ввести адрес заново":
        await state.set_state(AuthFSM.entering_email)
        await message.answer(
            text=chat.not_auth_msg,
            reply_markup=ReplyKeyboardRemove()
        )
    elif text == "Подтвердить":
        user_email = (await state.get_data())["user_email"]
        user = await User.auth(user_email, message)
        await state.clear()
        await message.answer(
            text=chat.auth_message(user.email, user.is_admin),
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await message.answer("Выберите, Подтвердить или Ввести адрес заново")
