import inspect
import json
import logging
from datetime import datetime
from enum import Enum
from os import getenv
from typing import Optional, Self

from aiogram.types import Message
from sqlalchemy import ForeignKey, select, or_
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.sql.operators import ilike_op

SECRETS_IN_FILE = getenv("SECRETS_IN_FILE")
if SECRETS_IN_FILE == "true":
    SECRETS_ADDRESS = getenv("SECRETS_ADDRESS")
    PG_DB_NAME = open(f"{SECRETS_ADDRESS}/pg_db_name").readline()
    PG_USER = open(f"{SECRETS_ADDRESS}/pg_user").readline()
    PG_PASSWORD = open(f"{SECRETS_ADDRESS}/pg_pass").readline()
else:
    PG_DB_NAME = getenv("PG_DB_NAME")
    PG_USER = getenv("PG_USER")
    PG_PASSWORD = getenv("PG_PASSWORD")

DB_HOST = getenv("POSTGRES_URL")

engine = create_async_engine(f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@{DB_HOST}/{PG_DB_NAME}")

CATEGORIES = ["ККТ", "Весы", "Принтер кухонный", "Планшет", "Терминал", "Эквайринг", "Сканер", "Другое"]


class Base(AsyncAttrs, DeclarativeBase):

    @classmethod
    async def add_existed(cls, model) -> Self:
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                model = await session.merge(model)
                session.add(model)
                await session.commit()
                return model

    @classmethod
    async def get_all(cls, limit: int = 100) -> list[Self]:
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                stmt = select(cls).limit(limit)
                result = await session.scalars(stmt)
                objects = result.all()
                return list(objects)

    @classmethod
    async def get(cls, name_and_value: dict, limit=100) -> list[Self]:
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                stmt = select(cls).filter_by(**name_and_value).limit(limit)
                result = await session.scalars(stmt)
                objects = result.all()
                return list(objects)

    @classmethod
    async def get_by_primary(cls, value) -> list[Self]:
        primary_field_name = ""
        members = inspect.getmembers(cls)
        for name, member in members:
            if hasattr(member, "primary_key") and getattr(member, "primary_key"):
                primary_field_name = name
        if primary_field_name == "":
            raise ValueError(f"Не найден primary key для класса {cls}")
        return await cls.get({primary_field_name: value})

    @classmethod
    def get_fields_names(cls) -> list[str]:
        return cls.__table__.columns.keys()

    @classmethod
    def get_fields(cls) -> dict[str, str | None]:
        return {field: None for field in cls.get_fields_names()}

    @classmethod
    def _prepare_filters_for_strings(cls, fields: list[str], search_key: str) -> list:
        search_filter = list()
        for field in fields:
            atr = getattr(cls, field)
            search_filter.append(ilike_op(atr, f"%{search_key}%"))
            search_filter.append(ilike_op(atr, f"%{search_key.capitalize()}%"))
            search_filter.append(ilike_op(atr, f"%{search_key.upper()}%"))
        return search_filter


class ActionType(str, Enum):
    TAKE = "Взять: /take",
    QUEUE = "Встать в очередь: /queue",
    RETURN = "Вернуть: /return",
    LEAVE = "Покинуть очередь: /leave"
    EDIT = "Отредактировать: /edit"


class Action(Base):
    __tablename__ = "action"

    type: Mapped[ActionType] = mapped_column(primary_key=True, unique=True)

    def __repr__(self):
        return f"Action(type={self.type})"

    def __str__(self):
        return f"Действие {self.type})"


class Record(Base):
    __tablename__ = "record"

    id: Mapped[int] = mapped_column(primary_key=True)
    resource: Mapped[str] = mapped_column(ForeignKey("resource.id", onupdate="cascade", ondelete="cascade"))
    user_email: Mapped[str] = mapped_column(ForeignKey("visitor.email", onupdate="cascade", ondelete="cascade"))
    action: Mapped[Action] = mapped_column(ForeignKey("action.type", onupdate="cascade", ondelete="cascade"))
    time: Mapped[datetime] = mapped_column(server_default=func.now())

    def __repr__(self):
        return f"Record(id={self.id}, " \
               f"resource={self.resource}" \
               f"user_email={self.user_email}" \
               f"action={self.action}" \
               f"time={self.time})"

    def __str__(self):
        return f"Запись с id {self.id}: " \
               f"пользователь с почтой {self.user_email} " \
               f"выполнил действие {self.action} " \
               f"над ресурсом {self.resource} " \
               f"в момент {self.time}"

    @classmethod
    async def delete(cls, **fields) -> bool:
        for field in fields.keys():
            if field not in cls.get_fields_names():
                logging.error(f"В метод Record.delete некорректно передано поле field: {field}")
                return False
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                records = await cls.get(fields)
                if len(records) == 0:
                    return False
                await session.delete(records[-1])
                await session.commit()
        return True

    @classmethod
    async def add(cls, resource_id, email, action: ActionType) -> "Record":
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                record = Record(**{"resource": resource_id, "user_email": email, "action": action})
                session.add(record)
                await session.commit()
                return record


class Visitor(Base):
    __tablename__ = "visitor"

    email: Mapped[str] = mapped_column(primary_key=True)
    is_admin: Mapped[bool] = mapped_column(default=False)
    chat_id: Mapped[Optional[int]] = mapped_column()
    user_id: Mapped[Optional[int]] = mapped_column()
    full_name: Mapped[Optional[str]] = mapped_column()
    username: Mapped[Optional[str]] = mapped_column()
    comment: Mapped[Optional[str]] = mapped_column()
    resources = relationship("Resource")
    records = relationship("Record")

    def __repr__(self):
        return f"Visitor(name={self.email}, " \
               f"chat_id={self.chat_id or 'None'}, " \
               f"is_admin={self.is_admin}, " \
               f"user_id={self.user_id or 'None'}, " \
               f"full_name={self.full_name or 'None'}, " \
               f"username={self.username or 'None'}, " \
               f"comment={self.comment or 'None'})"

    def __str__(self):
        return f"Пользователь с почтой {self.email} " \
               f"с chat_id {self.chat_id or 'None'} и " \
               f"{'c админскими правами' if self.is_admin else 'без админских прав'}"

    @classmethod
    async def auth(cls, email: str, message: Message) -> "Visitor":
        with open("config.json", "r", encoding="utf-8") as file:
            data = json.loads(file.read())
            is_admin = email in data["admins"]
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                stmt = select(cls).where(cls.email == email)
                result = await session.scalars(stmt)
                users_with_email = result.all()
                if len(users_with_email) != 0:
                    users_with_email[0].chat_id = message.chat.id
                    await session.commit()
                    logging.info(f"Пользователь изменил chat_id: {repr(users_with_email[0])}")
                    return users_with_email[0]
                else:
                    user = Visitor(
                        email=email,
                        chat_id=message.chat.id,
                        is_admin=is_admin,
                        user_id=message.from_user.id,
                        full_name=message.from_user.full_name,
                        username=message.from_user.username)
                    session.add(user)
                    await session.commit()
                    logging.info(f"Пользователь авторизовался: {repr(user)}")
                    return user

    @classmethod
    async def update_email(cls, current_email, new_email):
        visitors = await cls.get_by_primary(current_email)
        if len(visitors) == 0:
            return None
        visitor = visitors[0]
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                visitor = await session.merge(visitor)
                visitor.email = new_email
                await session.commit()
        return True

    @classmethod
    async def get_current(cls, chat_id: int) -> "Visitor | None":
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                stmt = select(cls).filter_by(chat_id=chat_id)
                result = await session.scalars(stmt)
                users = result.all()
                if len(users) != 0:
                    return users[0]
        logging.error(f"Не найден пользователь с chat_id: {chat_id}")
        return None

    @classmethod
    async def is_exist(cls, chat_id: int) -> bool:
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                stmt = select(cls).where(cls.chat_id == chat_id)
                result = await session.scalars(stmt)
                users = result.all()
        return len(users) == 1

    @classmethod
    async def add_if_needed(cls, email: str) -> bool:
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                stmt = select(cls).where(cls.email == email)
                result = await session.scalars(stmt)
                users = result.all()
                if len(users) > 0:
                    return False
                session.add(Visitor(email=email))
                await session.commit()
                return True


class Category(Base):
    __tablename__ = "category"

    name: Mapped[str] = mapped_column(primary_key=True, unique=True)

    def __repr__(self):
        return f"Category(name={self.name})"

    def __str__(self):
        return f"Категория {self.name}"

    @classmethod
    async def add(cls, category_name: str) -> None:
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                stmt = select(Category).where(Category.name == category_name)
                result = await session.scalars(stmt)
                categories = result.all()
                if len(categories) == 0:
                    session.add(Category(name=category_name))
                await session.commit()


class Resource(Base):
    __tablename__ = "resource"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    category_name: Mapped[str] = mapped_column(ForeignKey("category.name"))
    vendor_code: Mapped[str] = mapped_column(unique=True)
    reg_date: Mapped[Optional[datetime]] = mapped_column()
    firmware: Mapped[Optional[str]] = mapped_column()
    comment: Mapped[Optional[str]] = mapped_column()
    user_email: Mapped[Optional[str]] = mapped_column(
        ForeignKey("visitor.email", onupdate="cascade", ondelete="cascade"))
    address: Mapped[Optional[str]] = mapped_column()
    return_date: Mapped[Optional[datetime]] = mapped_column()

    def __repr__(self):
        return f"Resource(id={self.id}, " \
               f"name={self.name}, " \
               f"category_name={self.category_name}, " \
               f"vendor_code={self.vendor_code}, " \
               f"user_email={self.user_email or 'None'})"

    def __str__(self):
        return ("".join(
            [
                f"{self.id}\r\n",
                f"{self.name} ({self.category_name.lower()})\r\n",
                f"Артикул (ЗН или СН): {self.vendor_code}\r\n",
                f"Зарегистрирован {self.reg_date.strftime(r'%d.%m.%Y')}\r\n" if self.reg_date is not None else "",
                f"Комментарий: {self.comment}\r\n" if self.comment is not None else "",
                f"Прошивка: {self.firmware}\r\n" if self.firmware is not None else "",
                f"Сейчас у пользователя: {self.user_email}\r\n" if self.user_email is not None else "",
                f"Освободится примерно: {self.return_date.strftime(r'%d.%m.%Y')}\r\n" if self.return_date is not None else "",
                f"Где находится: {self.address}\r\n" if self.address is not None else "",
            ]))[:-2]

    @classmethod
    async def get_single(cls, resource_id) -> "Resource | None":
        resources = await Resource.get_by_primary(resource_id)
        if len(resources) == 0:
            logging.error(f"Не найден ресурс с resource_id={resource_id}")
            return None
        return resources[0]

    @classmethod
    async def update(cls, resource_id: int, **fields) -> "Resource | None":
        for field in fields.keys():
            if field not in Resource.get_fields_names():
                logging.error(f"В метод Resource.update некорректно передано поле field: {field}")
                return None
        if "user_email" in fields.keys() and fields["user_email"] is not None:
            await Visitor.add_if_needed(email=fields["user_email"])
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        resources = await Resource.get_by_primary(resource_id)
        resource = resources[0]
        async with async_session() as session:
            async with session.begin():
                resource = await session.merge(resource)
                for field, value in fields.items():
                    setattr(resource, field, value)
                await session.commit()
        return resource

    @classmethod
    async def add(cls, **fields) -> "Resource | None":
        for field in fields.keys():
            if field not in Resource.get_fields_names():
                logging.error(f"В метод Resource.update некорректно передано поле field: {field}")
                return None
        if "name" not in fields.keys() or "category_name" not in fields.keys() or "vendor_code" not in fields.keys() or "id" not in fields.keys():
            logging.error(f"При добавлении ресурса в метод не переданы name, category_name, "
                          f"vendor_code или id. Значение fields: {fields}")
            return None
        if "user_email" in fields.keys() and fields["user_email"] is not None:
            await Visitor.add_if_needed(email=fields["user_email"])
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                resource = Resource(**fields)
                session.add(resource)
                await session.commit()
                return resource

    @classmethod
    async def take(cls, resource_id, user_email, address=None, return_date=None) -> "Resource | None":
        resources = await cls.get({"id": resource_id})
        if len(resources) == 0:
            logging.error(f"Не найдено устройство с resource_id {resource_id}, "
                          f"пользователь {user_email} будет расстроен")
            return None
        resource = resources[0]
        await Visitor.add_if_needed(email=user_email)
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                resource = await session.merge(resource)
                resource.user_email = user_email
                resource.address = address
                resource.return_date = return_date
                await session.commit()
                return resource

    @classmethod
    async def free(cls, resource_id) -> "Resource":
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                stmt = select(cls).where(cls.id == resource_id)
                result = await session.scalars(stmt)
                resources = result.all()
                resource = resources[0]
                resource.user_email = None
                resource.address = None
                resource.return_date = None
                await session.commit()
                return resource

    @classmethod
    async def search(cls, search_key: str, limit=100) -> "list[Resource]":
        if search_key.isnumeric() and int(search_key) < 1000000:
            filters = [Resource.id.in_([int(search_key)])]
        else:
            filters = cls._prepare_filters_for_strings(
                fields=["name", "category_name", "user_email", "vendor_code"],
                search_key=search_key
            )
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                stmt = select(cls).filter(or_(*filters)).limit(limit)
                result = await session.scalars(stmt)
                resources = result.all()
                return list(resources)

    @classmethod
    async def delete(cls, id) -> None:
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                resource = (await cls.get_by_primary(id))[0]
                await session.delete(resource)
                await session.commit()

    @classmethod
    async def get_resources_taken_by_user(cls, user) -> "list[Resource]":
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                stmt = select(cls).where(cls.user_email == user.email)
                result = await session.scalars(stmt)
                resources = result.all()
                return list(resources)

    @classmethod
    async def get_by_vendor_code(cls, vendor_code) -> "list[Resource]":
        return await Resource.get({"vendor_code": vendor_code})

    @classmethod
    async def get_categories(cls) -> "list[str]":
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                stmt = select(cls).with_only_columns(cls.category_name).distinct()
                result = await session.scalars(stmt)
                resources = result.all()
                return list(resources)

    async def get_csv_value(self) -> list[str]:
        return [
            str(self.id),
            self.name,
            self.category_name,
            self.vendor_code,
            self.reg_date.strftime(r'%d.%m.%Y') if self.reg_date is not None else " ",
            self.firmware if self.firmware is not None else " ",
            self.comment if self.comment is not None else " ",
            self.user_email if self.user_email is not None else " ",
            self.address if self.address is not None else " ",
            self.return_date.strftime(r'%d.%m.%Y') if self.return_date is not None else " "
        ]


class BDInit:

    @classmethod
    async def init(cls) -> None:
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                stmt = select(Action)
                result = await session.scalars(stmt)
                actions = result.all()
                if len(actions) != 0:
                    return
                for action in ActionType:
                    session.add(Action(type=action))
                for category in CATEGORIES:
                    session.add(Category(name=category))
                await session.commit()

    @classmethod
    async def prepare_test_data(cls) -> None:
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                stmt = select(Visitor)
                result = await session.scalars(stmt)
                users = result.all()
                if len(users) != 0:
                    return
                session.add_all(
                    [
                        Visitor(chat_id=230809906, email="mnoskov@skbkontur.ru", is_admin=True),
                        Visitor(chat_id=38170680, email="a.karamova@skbkontur.ru"),
                    ]
                )
                await session.commit()
        await Resource.add(**{"id": 1, "name": "Рыжик", "category_name": "ККТ", "vendor_code": "49494"})
        await Resource.take(1, "a.karamova@skbkontur.ru", "Берлога Пуриков", datetime(2024, 12, 18))
        await Resource.add(**{"id": 2, "name": "Сигма", "category_name": "Сканер", "vendor_code": "222"})
        await Resource.take(2, "mnoskov@skbkontur.ru")
        await Resource.add(**{"id": 3, "name": "Штрих-Слим", "category_name": "Весы", "vendor_code": "2223"})
        await Record.add(2, "a.karamova@skbkontur.ru", ActionType.QUEUE)

        # for i in range(20):
        #     await Resource.add(**{"name": f"Вертолет{i}",
        #                           "category_name": "ККТ",
        #                           "vendor_code": f"{i + 999}",
        #                           "user_email": "a.karamova@skbkontur.ru"})
