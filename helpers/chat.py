from aiogram.types import Message

from helpers.checker import ResourceError
from models import Resource


def get_word_ending(count: int, variants: list[str]) -> str:
    """
    Возвращает окончание слова в зависимости от количества.
    :variants - варианты окончания, первое - например, для количества 1, второе для 2, третье для 5
    """
    count = count % 100
    if 11 <= count <= 19:
        return variants[2]
    count = count % 10
    if count == 1:
        return variants[0]
    elif count in [2, 3, 4]:
        return variants[1]
    return variants[2]


def get_username_str(message: Message) -> str:
    if message.from_user:
        return f" {message.from_user.username} "
    return ' '


def get_take_from_user_msg(email: str, resource: Resource) -> str:
    return f"Вы списали устройство {resource.name} c артикулом {resource.vendor_code} с пользователя {email}. " \
           f"Напомните ему, чтобы в следующий раз сам отмечался в боте, не зря ж мы его делали :)"


def get_pass_to_user_msg(resource: Resource) -> str:
    return f"Вы записали устройство {resource.name} с артикулом {resource.vendor_code} " \
           f"на пользователя {resource.user_email}"


welcome_msg = "Добро пожаловать в бот кассового зоопарка!\r\n" \
              "Для поиска техники - введите серийный номер " \
              "или отсканируйте QR-код на устройстве и нажмите Start\r\n\r\n" \
              "Также вам помогут три команды:\r\n" \
              "/all - вся техника\r\n" \
              "/categories - по категориям\r\n" \
              "/mine - записанная на вас\r\n" \
              "/wishlist - за какими устройствами вы в очереди"

admin_welcome_msg = "Вы смотритель кассового зоопарка, поэтому вам доступны " \
                    "две дополнительных команды, скрытых из меню:\r\n" \
                    "/add - для добавления устройств\r\n" \
                    "/info - для скачивания логов\r\n\r\n" \
                    "Также вы можете написать рабочую почту пользователя и увидеть, какие он взял устройства"


def auth_message(user_email: str, is_admin: bool) -> str:
    return f"Вы авторизовались как {user_email}!\r\n\r\n" \
           f"{admin_welcome_msg if is_admin else welcome_msg}"


delete_success_msg = "Вы успешно удалили устройство"
edit_success_msg = "Вы отредактировали запись"
cancel_msg = "Вы отменили действие"

not_auth_msg = "Чтобы авторизоваться, ведите адрес своей контуровской почты в формате email@skbkontur.ru"
ask_confirm_auth = "Подтвердите, что это ваш адрес: изменить его в будущем не получится.\r\n" \
                   "Да, мы не проверяем, чей адрес введен, все на доверии :)"
not_admin_error_msg = "Действие доступно только админу. Обратитесь к автору бота, @misha_voyager"
wrong_email_msg = "Укажите именно контуровскую почту, чтобы мы идентифицировали вас однозначно :)"

ask_vendor_code_msg = "Укажите артикул устройства"
ask_name_msg = "Напишите название устройства. Например, MSPOS-N"
ask_category_msg = "Выберите категорию из списка ниже"
ask_email_msg = "Напишите email пользователя, у которого сейчас устройство, в формате email@skbkontur.ru"
ask_address_msg = "Где пользователь хранит устройство? Например, дома у Пети"
ask_return_date_msg = "Когда пользователь вернет устройство? Напишите примерную дату, например, 23.11.2024"
ask_reg_date_msg = "Введите дату регистрации устройства. Например, 28.01.2024"
ask_firmware_msg = "Укажите, какая прошивка на устройстве? Например: Прошивка 5.8.100, ДТО 10.9.0.10"
ask_comment_msg = "Введите комментарий к устройству. Например: Вернули в Атол (по договору тестирования)"

ask_way_of_adding_msg = "Выберите, добавить устройства по одному или загрузить файл в формате csv"
ask_file_msg = "Загрузите файл в формате csv. Максимум у вас получится 9 столбцов:\r\n\r\n" \
               "Название, Категория, Артикул, Дата регистрации, Прошивка, Комментарий, " \
               "Электронная почта, Место устройства, Дата возврата\r\n\r\n" \
               "Первые 3 поля обязательные, остальные можно оставить пустыми.\r\n" \
               "Пример строчки: MSPOS-N, ККТ, 4894892299, 18.05.2024, 12-8541, ,email@skbkontur.ru"
confirm_adding_msg = "Точно-точно добавить устройство?"

unexpected_action_msg = "Если тестили, автор жмет вам руку, если неожиданная ошибка - свяжитесь с @misha_voyager"
pass_date_error_msg = f"{ResourceError.PASSED_DATE.value}. Пожалуйста, поделитесь маховиком времени с автором бота"
not_found_msg = "Устройство не найдено, попробуйте поискать по-другому"
user_have_no_device_msg = "На вас не записано ни одно устройство. Спите спокойно, Эдуард не держит вас на карандашике"
empty_wishlist = "Вы не стоите в очереди ни на одно устройство"
return_others_device_msg = "Это устройство не записано на вас! " + unexpected_action_msg
leaving_queue_error_msg = "Не удалось покинуть очередь за устройством. " + unexpected_action_msg
unexpected_resource_not_found_error_msg = "Устройство не найдено. " + unexpected_action_msg
adding_file_error_msg = "При обработке файла произошла неожиданная ошибка. " \
                        "Попробуйте снова и, если повторится, обратитесь к автору бота, @misha_voyager"
wrong_file_format_msg = "Файл должен быть в формате .csv! Если у вас excel, просто экспортируйте его в нужном формате"
delete_taken_error_msg = "Устройство занял пользователь. " \
                         "Нельзя удалить его сейчас, сначала спишите его с пользователя"
take_taken_error_msg = "Устройство уже занято! Снова выполните поиск, чтобы посмотреть, на кого оно записано"
take_nonnexisted_error_msg = "Устройство не найдено, обратитесь к автору бота, @misha_voyager"
queue_second_time_error_msg = "Вы уже стоите в очереди на устройство, нельзя войти в одну реку дважды, как и вернуть 2007"
leave_left_error_msg = "Покинуть очередь не удалось: вас в ней не было. " \
                       "Заигрались в путешествия во времени и опять перепутали порядок событий?"
