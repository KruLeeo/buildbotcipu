from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from db_manager import db


class StatsMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Update):
            user = None
            event_type = "update"
            if event.message and event.message.from_user:
                user = event.message.from_user
                event_type = "message"
            elif event.callback_query and event.callback_query.from_user:
                user = event.callback_query.from_user
                event_type = "callback"
            if user:
                db.touch_user(user.id, user.username, user.first_name)
                db.record_event(event_type, user.id)
        return await handler(event, data)
