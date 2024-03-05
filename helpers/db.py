import logging

from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from models import Resource, User, Record, ActionType, engine


async def get_waited_resources_for_user(user: User):
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        async with session.begin():
            stmt1 = select(Record).where(Record.user_email == user.email,
                                         Record.action == ActionType.QUEUE).with_only_columns(Record.resource)
            result1 = await session.scalars(stmt1)
            resource_ids = result1.all()
            stmt2 = select(Resource).filter(Resource.id.in_(resource_ids))
            result2 = await session.scalars(stmt2)
            resources = result2.all()
    return resources


async def notify_user_about_returning(message: Message, email: str, resource: Resource) -> None:
    users: list[User] = (await User.get_by_primary(email))
    if len(users) == 0:
        logging.error(f"Не нашли пользователя {email}, чтобы уведомить о списании с него "
                      f"устройства {repr(resource)}")
        return None
    chat_id = users[0].chat_id
    await message.bot.send_message(chat_id,
                                   f"С вас списали устройство {resource.name} с артикулом {resource.vendor_code}\r\n"
                                   f"Если это ошибка, напишите @misha_voyager"
                                   )


async def notify_user_about_taking(message: Message, email: str, resource: Resource) -> None:
    users: list[User] = (await User.get_by_primary(email))
    if len(users) == 0:
        logging.info(f"Из-за ошибки авторизации не удалось уведомить пользователя с почтой {email} "
                     f"о записи на него устройства {repr(resource)}")
        return None
    chat_id = users[0].chat_id
    await message.bot.send_message(chat_id,
                                   f"На вас записали устройство {resource.name} c артикулом {resource.vendor_code}\r\n"
                                   f"/return{resource.id} - если уже неактуально.\r\n"
                                   f"А если это ошибка, напишите @misha_voyager"
                                   )


async def notify_next_user_about_taking(message: Message, next_user_email: str, resource: Resource) -> None:
    users: list[User] = (await User.get_by_primary(next_user_email))
    if len(users) == 0:
        logging.error(f"Не нашли пользователя {next_user_email}, чтобы уведомить "
                      f"о записи на него ресурса: {repr(resource)}")
        return None
    next_user_chat_id = users[0].chat_id
    await message.bot.send_message(
        next_user_chat_id,
        f"Записали на вас устройство {resource.name} c артикулом {resource.vendor_code}. Нажмите:\r\n"
        f"/update_address{resource.id} - если подтверждаете,\r\n"
        f"/return{resource.id} - если уже неактуально"
    )


async def pass_resource_to_next_user(resource_id) -> str | None:
    next_user_email = None
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        async with session.begin():
            stmt = select(Record).where(Record.resource == resource_id, Record.action == ActionType.QUEUE)
            result = await session.scalars(stmt)
            queue = result.all()
            if len(queue) != 0:
                record_with_next_user: Record = queue[-1]
                next_user_email = record_with_next_user.user_email
                resource = await Resource.take(resource_id=resource_id, user_email=record_with_next_user.user_email)
                record = await Record.add(resource_id, record_with_next_user.user_email, ActionType.TAKE)
                await session.delete(record_with_next_user)
                await session.commit()
                logging.info(
                    f"После возврата автоматически записалось на пользователя устройство: {repr(resource)}"
                )
                logging.info(
                    f"При передаче устройства следующему пользователю {next_user_email} была автоматически удалена "
                    f"запись QUEUE от даты {record_with_next_user.time} и добавлена запись TAKE от даты {record.time}")
    return next_user_email


async def get_resource_queue(resource_id) -> list[Record]:
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        async with session.begin():
            stmt = select(Record).where(Record.resource == resource_id, Record.action == ActionType.QUEUE)
            result = await session.scalars(stmt)
            queue = result.all()
    return list(queue)


async def is_user_in_queue(user: User, resource: Resource, records: list[Record] = None) -> bool:
    if not records:
        records = await Record.get({"user_email": user.email})
    user_in_queue = False
    for record in records:
        if record.user_email == user.email and record.resource == resource.id and record.action == ActionType.QUEUE:
            user_in_queue = True
    return user_in_queue


async def get_available_action(resource: Resource, chat_id) -> ActionType:
    user = await User.get_current(chat_id)
    records: list[Record] = await Record.get({"user_email": user.email})
    if not resource.user_email:
        return ActionType.TAKE
    elif resource.user_email == user.email:
        return ActionType.RETURN
    elif await is_user_in_queue(user, resource, records):
        return ActionType.LEAVE
    else:
        return ActionType.QUEUE


async def format_note(resource: Resource, chat_id) -> str:
    command = (await get_available_action(resource, chat_id)).value
    user = await User.get_current(str(chat_id))
    if user.is_admin:
        return f"{str(resource)}\r\n{command}{resource.id}\r\n{ActionType.EDIT.value}{resource.id}\r\n\r\n"
    else:
        return f"{str(resource)}\r\n{command}{resource.id}\r\n\r\n"


async def format_notes(resources: list[Resource], chat_id) -> str:
    return "".join([await format_note(resource, chat_id) for resource in resources])


def get_field_name(field) -> str:
    return str(field).split(".")[1]


async def return_resource(resource_id) -> None:
    resources = await Resource.get_by_primary(resource_id)
    resource = resources[0]
    await Resource.free(resource_id)
    await Record.delete(**{
        get_field_name(Record.resource): resource_id,
        get_field_name(Record.action): ActionType.TAKE,
        get_field_name(Record.user_email): resource.user_email})
