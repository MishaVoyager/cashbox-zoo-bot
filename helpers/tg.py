import math

from aiogram import types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from helpers import db, chat


def get_reply_keyboard(elements: list[str]) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for element in elements:
        builder.button(text=f"{element}")
    builder.adjust(2)
    return builder.as_markup()


def get_inline_keyboard(elements: list[str], callback_data: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for element in elements:
        builder.row(types.InlineKeyboardButton(
            text=f"{element}",
            callback_data=f"{callback_data} {element}")
        )
    builder.adjust(2)
    return builder.as_markup()


class Paginator:

    def __repr__(self):
        return f"Paginator(page={self.page}, " \
               f"visible_results={self.visible_results}, " \
               f"page_elements={self.page_elements}, " \
               f"pages={self.pages}, " \
               f"len objects={len(self.objects)})"

    def __str__(self):
        return f"Пагинатор для страницы {self.page}: " \
               f"количество элементов {self.page_elements}, " \
               f"количество видимых страниц {self.visible_results}"

    def __init__(self, page: int, objects: list, visible_results: int = 5, page_elements: int = 5):
        self.objects = objects
        self.pages = math.ceil(len(objects) / visible_results)
        self.visible_results = visible_results
        self.page_elements = page_elements
        self.page = page

    def get_pages_numbers(self) -> tuple[int | None, ...]:
        """Возвращает кортеж номеров страниц, например (1, 2, 3) или (None, None, None)"""
        if self.page > self.pages:
            raise AssertionError("Номер страницы не может быть выше максимального")
        if self.page == self.pages == 1:
            return tuple([None] * self.page_elements)
        result = [i + self.page for i in range(self.page_elements)]
        while result[-1] > min(self.pages, self.page + int(self.page_elements / 2)) and result[-1] > self.page_elements:
            result = list(map(lambda x: x - 1, result))
        return tuple(map(lambda x: x if x <= self.pages else None, result))

    def create_keyboard(self, page_handle: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        page_numbers = self.get_pages_numbers()
        [self._create_page_button(builder, number, page_handle) for number in page_numbers if number]
        builder.adjust(self.page_elements)
        return builder.as_markup()

    def _create_page_button(self, builder: InlineKeyboardBuilder, number: int,
                            page_handle: str) -> InlineKeyboardBuilder:
        builder.row(types.InlineKeyboardButton(
            text=f"{number}" if number != self.page else f"-{number}-", callback_data=f"{page_handle} {number}"))
        return builder

    def get_objects_on_page(self) -> list:
        left, right = self.get_array_indexes()
        return self.objects[left: right + 1]

    def get_array_indexes(self) -> tuple[int, int]:
        left_index = 0 + self.visible_results * (self.page - 1)
        right_index = min((self.visible_results - 1) + self.visible_results * (self.page - 1), len(self.objects) - 1)
        return left_index, right_index

    def result_message(self) -> str:
        count = len(self.objects)
        return f"Всего найден{chat.get_word_ending(count, ['', 'о', 'о'])} " \
               f"{count} результат{chat.get_word_ending(count, ['', 'а', 'ов'])}:\r\n\r\n"


async def get_standard_paginator(page, resources, command_name, chat_id) -> tuple[str, InlineKeyboardMarkup]:
    paginator = Paginator(page, resources)
    keyboard = paginator.create_keyboard(command_name)
    notes = await db.format_notes(paginator.get_objects_on_page(), chat_id)
    reply = paginator.result_message() + notes
    return reply, keyboard
