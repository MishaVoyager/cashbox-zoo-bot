import logging
import re
from collections import Counter
from datetime import datetime
from enum import Enum
from re import Match

import models


class ResourceError(str, Enum):
    WRONG_ID = "Айди ресурса не является числом"
    EXISTED_ID = "Уже есть устройства с таким айди"
    NO_ID = "Не указан id ресурса"
    NO_NAME = "Не указано название ресурса"
    NO_CATEGORY = "Не указана категория ресурса"
    NO_VENDOR_CODE = "Не указан артикул"
    WRONG_EMAIL = "Почта не соответствует формату email@skbkontur.ru",
    PASSED_DATE = "Дата из прошлого"
    WRONG_DATE = "Дата не соответствует формату: дд.мм.гггг"
    EXISTED_VENDOR_CODE = "Уже есть устройства с таким артикулом"
    UNEXPECTED = "Произошла неизвестная ошибка, обратитесь к автору бота, @misha_voyager"
    WRONG_CATEGORY = "Такой категории не существует"


async def is_admin(chat_id) -> bool:
    user = await models.Visitor.get_current(chat_id)
    return user.is_admin


async def is_existed_vendor_code(vendor_code: str) -> bool:
    existed_resources: list[models.Resource] = await models.Resource.get_by_vendor_code(vendor_code)
    return len(existed_resources) >= 1


async def is_existed_id(resource_id: int) -> bool:
    existed_resources: list[models.Resource] = await models.Resource.get_by_primary(resource_id)
    return len(existed_resources) >= 1


def prepare_fields(row: list[str]) -> dict[str, str | None]:
    row_with_none = [x.strip() if x.strip() != "" else None for x in row]
    fields = models.Resource.get_fields()
    for index, key_value in enumerate(fields.items()):
        if index >= len(row_with_none):
            break
        fields.update({key_value[0]: row_with_none[index]})
    return fields


async def check_resource(
        id: str,
        name: str,
        category_name: str,
        vendor_code: str,
        reg_date: str,
        firmware: str,
        comment: str,
        user_email: str,
        address: str,
        return_date: str) -> tuple[models.Resource | None, list[ResourceError]]:
    errors = []
    if not id:
        errors.append(ResourceError.NO_ID)
    else:
        if not id.isnumeric():
            errors.append(ResourceError.WRONG_ID)
        else:
            id = int(id)
            if await is_existed_id(id):
                errors.append(ResourceError.EXISTED_ID)
    if not vendor_code:
        errors.append(ResourceError.NO_VENDOR_CODE)
    else:
        if await is_existed_vendor_code(vendor_code):
            errors.append(ResourceError.EXISTED_VENDOR_CODE)
    if not name:
        errors.append(ResourceError.NO_NAME)
    if not category_name:
        errors.append(ResourceError.NO_CATEGORY)
    else:
        if not await is_right_category(category_name):
            errors.append(ResourceError.WRONG_CATEGORY)
    if reg_date:
        reg_date = try_convert_to_ddmmyyyy(reg_date)
        if not reg_date:
            errors.append(ResourceError.WRONG_DATE)
    if user_email and not is_kontur_email(user_email):
        errors.append(ResourceError.WRONG_EMAIL)
    if return_date:
        return_date = try_convert_to_ddmmyyyy(return_date)
        if not return_date:
            errors.append(ResourceError.WRONG_DATE)
        elif is_paste_date(return_date):
            errors.append(ResourceError.PASSED_DATE)
    if len(errors) == 0:
        resource = models.Resource(
            id=id,
            name=name,
            category_name=category_name,
            vendor_code=vendor_code,
            reg_date=reg_date,
            firmware=firmware,
            comment=comment,
            user_email=user_email,
            address=address,
            return_date=return_date
        )
        logging.info(f"Обработали ресурс: {repr(resource)}")
    else:
        resource = None
    return resource, errors


def get_vendor_code_doubles(resources: list) -> list:
    if len(resources) == 0:
        return []
    vendor_codes = [i.vendor_code for i in resources]
    return [k for k, v in Counter(vendor_codes).items() if v > 1]


def get_resource_id_doubles(resources: list) -> list:
    if len(resources) == 0:
        return []
    resource_ids = [i.id for i in resources]
    return [k for k, v in Counter(resource_ids).items() if v > 1]


def get_doubles_text(doubles: list, field_name: str) -> str:
    return f"В файле есть дубли {field_name} {', '.join(doubles)}" if len(doubles) != 0 else ""


def format_errors(indexes_with_errors: dict[int, list[ResourceError]]) -> str:
    errors_text = ""
    for row, errors in indexes_with_errors.items():
        errors_text += f"В строке {row}:\r\n" + "\r\n".join([i.value for i in errors]) + "\r\n\r\n"
    return errors_text


async def is_right_category(category: str) -> bool:
    available_categories = [i.name for i in (await models.Category.get_all())]
    return category in available_categories


def try_convert_to_ddmmyyyy(date: str) -> datetime | None:
    if not re.search(r"^\d{2}.\d{2}.\d{4}$", date):
        return None
    day, month, year = map(int, date.split("."))
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def is_valid_email(email: str) -> Match | None:
    return re.search(r"^\w+@\w+\.\w+$", email)


def is_kontur_email(email: str) -> Match | None:
    return re.search(r"^.*@((skbkontur)|(kontur))\.\w+$", email)


def is_paste_date(date: datetime) -> bool:
    return date.date() < datetime.now().date()
