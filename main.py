import asyncio
import logging
from logging.handlers import TimedRotatingFileHandler
from os import getenv

from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from handlers import backdoor, search, auth, add_resource, take, cancel, edit, actions
from models import Base, BDInit, engine

WEBHOOK_HOST = getenv("ZOO_WEBHOOK_PATH")
WEBHOOK_ROUTE = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_ROUTE}"
WEBHOOK_SECRET = getenv("ZOO_WEBHOOK_SECRET")

WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 8080

TOKEN = getenv("ZOO_TOKEN")
COMMANDS = [
    types.BotCommand(command="/all", description="Весь список устройств"),
    types.BotCommand(command="/categories", description="Поиск по рубрикам"),
    types.BotCommand(command="/mine", description="Мои устройства"),
    types.BotCommand(command="/wishlist", description="За какими устройствами вы в очереди"),
    types.BotCommand(command="/help", description="Как пользоваться ботом?")
]


async def init_base():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await BDInit.init()
    await BDInit.prepare_test_data()


async def main(on_server: bool = True):
    await init_base()
    bot = Bot(token=TOKEN)
    await bot.set_my_commands(COMMANDS)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(cancel.router)
    dp.include_router(backdoor.router)
    dp.include_router(auth.router)
    dp.include_router(add_resource.router)
    dp.include_router(take.router)
    dp.include_router(edit.router)
    dp.include_router(actions.router)
    dp.include_router(search.router)

    if not on_server:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        return

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL, secret_token=WEBHOOK_SECRET)

    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET)
    webhook_requests_handler.register(app, path=WEBHOOK_ROUTE)
    setup_application(app, dp, bot=bot)
    logging.info(f"Приложение запустилось на сервере. Хост: {WEBAPP_HOST}, порт: {WEBAPP_PORT}. "
                 f"URL вебхука: {WEBHOOK_HOST}")
    await web._run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        handlers=[TimedRotatingFileHandler(
            filename="logs/cashbox_zoo.log",
            when="midnight",
            backupCount=30,
            encoding="utf-8",
            utc=True
        )]
    )
    asyncio.run(main(on_server=True))
