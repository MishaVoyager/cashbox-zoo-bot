from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message

from models import Visitor


class AuthMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
            event: Message,
            data: Dict[str, Any]
    ) -> Any:
        if await Visitor.is_exist(event.chat.id):
            data["authorized"] = True
        result = await handler(event, data)
        return result
