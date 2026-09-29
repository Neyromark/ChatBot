from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.types import RequestContactButton, CallbackButton

from models import ROLE_OWNER, ROLE_ADMIN, ROLE_EMPLOYEE


class Texts():
    INTRO_TEXT = (
        "Здравствуйте! 👋\n"
        "Я бот для управления сменами, задачами и загрузкой сотрудников.\n"
        "Помогу администратору быстро составлять расписание и раздавать задачи, "
        "а сотрудникам — видеть свои дела и получать уведомления.\n"
        "Давайте познакомимся.\n"
        "Напишите, пожалуйста, ваше имя:"
    )

    ASK_LAST_NAME = "Отлично! Теперь напиши свою фамилию:"
    ASK_PHONE = "Спасибо! Теперь напиши номер телефона:"
    FINISH_TEXT = "Готово! Ты зарегистрирован ✅"
    INVALID_PHONE = "Похоже, это не похоже на номер телефона. Попробуй ещё раз:"
    SECOND_REGISTR = "Вы уже зарегистрированы. Напиши /start, чтобы начать заново."
    NO_COMPANI = "Вас, нет не в одной организации, хотите присоединиться или создать новую?"

    WAITING_NAME_COMPANI = "Введите название компании"
    WAITING_ORG_CITY = "Введите город в котором работает компания"
    WAITING_ORG_TYPE = "Введите тип организации"

    WAITING_COD_ORGANIZATION = "Введите код организации для присоединения (его можно узнать у руководителя организации)"

    PROFILE_TITLE = "👤 Ваш профиль"
    PROFILE_EDIT_NAME = "Введите новое имя:"
    PROFILE_EDIT_LAST_NAME = "Введите новую фамилию:"
    PROFILE_EDIT_PHONE = "Отправьте новый номер телефона"

    ANNOUNCEMENTS_TITLE = "Управление объявлениями"
    ANNOUNCEMENTS_ASK_TITLE = "Введите заголовок объявления:"
    ANNOUNCEMENTS_ASK_BODY = "Введите текст объявления:"
    ANNOUNCEMENTS_ASK_TARGET = "Кому отправить объявление?"
    ANNOUNCEMENTS_ASK_USERS = "Отметьте сотрудников, которым нужно доставить объявление, и нажмите «Готово»."
    ANNOUNCEMENTS_SAVED = "Объявление создано и отправлено."
    ANNOUNCEMENTS_EMPTY = "Объявлений пока нет."
    ANNOUNCEMENTS_UNREAD = "У вас {count} непрочитанных объявлений"

    ORG_INFO_TITLE = "Информация об организации"

    ORG_SETTINGS_TITLE = "Настройки организации"
    ORG_EDIT_NAME = "Введите новое название организации:"
    ORG_EDIT_CITY = "Введите новый город:"
    ORG_EDIT_TYPE = "Выберите новый тип организации:"
    ORG_UPDATED = "Настройки организации обновлены."
    ORG_NAME_INVALID = "Название не может быть пустым."

    ANN_TITLE = "Объявления"
    ANN_EMPTY = "У вас нет непрочитанных объявлений."
    ANN_SEARCH_TITLE = "Введите часть названия объявления для поиска:"
    ANN_SEARCH_DATE = "Введите дату в формате ГГГГ-ММ-ДД (например, 2026-09-27):"
    ANN_SEARCH_BY = "Как искать объявления?"
    ANN_SEARCH_INVALID_DATE = "Неверный формат даты. Используйте ГГГГ-ММ-ДД."
    ANN_NOT_FOUND = "Ничего не найдено."

    STAFF_TITLE = "Управление сотрудниками"
    STAFF_EMPTY = "В организации нет сотрудников."
    STAFF_LIST_HEADER = "Список сотрудников:\n"
    STAFF_ASK_NUMBER_FIRE = "Введите номер сотрудника, которого нужно уволить:"
    STAFF_ASK_NUMBER_ROLE = "Введите номер сотрудника, которому нужно изменить системную роль:"
    STAFF_ASK_NUMBER_NAME_ROLE = "Введите номер сотрудника, которому нужно изменить роль в организации:"
    STAFF_ASK_NEW_ROLE = "Выберите новую системную роль:"
    STAFF_ASK_NAME_ORG_ROLE = "Введите название роли в организации:"
    STAFF_BAD_NUMBER = "Неверный номер. Введите число из списка."
    STAFF_ROLE_UPDATED = "Системная роль обновлена."
    STAFF_NAME_ROLE_UPDATED = "Роль в организации обновлена."
    STAFF_FIRED = "Сотрудник уволен."
    STAFF_CANNOT_FIRE_SELF = "Нельзя уволить самого себя."
    STAFF_CANNOT_FIRE_OWNER = "Нельзя уволить владельца организации."

    TASKS_TITLE = "Управление задачами"
    TASKS_CREATE_TITLE = "Введите название задачи:"
    TASKS_CREATE_DESC = "Введите описание задачи (или «-», чтобы пропустить):"
    TASKS_CREATE_ASSIGNEE = "Кому назначить задачу?"
    TASKS_CREATE_ASSIGNEE_USER = "Введите номер сотрудника из списка:"
    TASKS_CREATE_WEIGHT = "Введите вес задачи (1–10):"
    TASKS_CREATE_MINUTES = "Введите оценочное время в минутах:"
    TASKS_CREATED = "Задача создана."
    TASKS_EMPTY_ACTIVE = "Сейчас никто не выполняет задачи."
    TASKS_EMPTY_POOL = "Нет свободных задач с дедлайном."
    TASKS_ASK_EDIT_NUMBER = "Введите номер задачи из списка:"
    TASKS_ASK_EDIT_FIELD = "Что изменить?"
    TASKS_ASK_NEW_TITLE = "Введите новое название:"
    TASKS_ASK_NEW_DESC = "Введите новое описание:"
    TASKS_ASK_NEW_WEIGHT = "Введите новый вес (1–10):"
    TASKS_ASK_NEW_MINUTES = "Введите новое оценочное время (минуты):"
    TASKS_UPDATED = "Задача обновлена."
    TASKS_BAD_NUMBER = "Неверный номер."

    TASK_TITLE = "1/9. Введите название задачи (3–200 символов):"
    TASK_DESCRIPTION = "2/9. Введите описание задачи:"
    TASK_ASSIGNEE = "3/9. Кому назначить задачу?"
    TASK_ORG_ROLE_NAME = "Введите название роли в организации (например, «Курьер»):"
    TASK_ORG_ROLE_NOT_FOUND = (
        "Сотрудников с такой ролью нет. "
        "Проверьте название или выберите другой вариант."
    )
    TASK_EXTERNAL_ROLE = "Введите название внешней должности (например, «Курьер»):"
    TASK_RECURRENCE = "4/9. Задача повторяется?"
    TASK_DEADLINE = "5/9. Введите дедлайн в формате ДД.ММ.ГГГГ ЧЧ:ММ"
    TASK_START_TIME_ASK = "6/9. Указать точное время начала?"
    TASK_START_TIME = "Введите время начала в формате ДД.ММ.ГГГГ ЧЧ:ММ"
    TASK_WEEKDAYS = "5/9. Выберите дни недели (можно несколько):"
    TASK_TIME = "6/9. Введите дедлайн — время суток, к которому задача должна быть выполнена (ЧЧ:ММ):"
    TASK_START_TIME_REGULAR = "Введите время начала (ЧЧ:ММ), раньше дедлайна:"
    TASK_START_BEFORE_DEADLINE = "Время начала должно быть раньше дедлайна. Введите время ещё раз."

    TASK_PERIOD_ASK = "8/9. Период действия правила:"
    TASK_PERIOD_START = "Введите дату начала (ДД.ММ.ГГГГ):"
    TASK_PERIOD_END = "Введите дату окончания (ДД.ММ.ГГГГ) или «-», если бессрочно:"
    TASK_ESTIMATED_MINUTES = "7/9. Оценочное время выполнения (в минутах):"
    TASK_WEIGHT = "8/9. Вес задачи (1–10):"
    TASK_CONFIRM_TITLE = "9/9. Проверьте данные задачи:"
    TASK_INVALID_TITLE = "Название должно быть от 3 до 200 символов."
    TASK_INVALID_DATETIME = "Неверный формат. Ожидается ДД.ММ.ГГГГ ЧЧ:ММ."
    TASK_INVALID_DATE = "Неверный формат даты. Ожидается ДД.ММ.ГГГГ."
    TASK_INVALID_TIME = "Неверный формат времени. Ожидается ЧЧ:ММ."
    TASK_INVALID_INT = "Введите целое число."
    TASK_INVALID_RANGE = "Значение вне допустимого диапазона."
    TASK_WEEKDAYS_MIN = "Выберите хотя бы один день недели."
    TASK_CANCELLED = "Создание задачи отменено."

    ANN_MY_TITLE = "Мои объявления"
    ANN_MY_EMPTY = "За этот день объявлений нет."
    ANN_MY_ASK_DATE = "Введите дату в формате ДД.ММ.ГГГГ:"
    ANN_MY_INVALID_DATE = "Неверный формат. Используйте ДД.ММ.ГГГГ."
    ANN_MY_NOT_FOUND = "Объявление не найдено."

    REPORT_TITLE = "Выгрузка отчётности"
    REPORT_CHOOSE = "Выберите тип отчёта:"
    REPORT_ASK_DATE_FROM = "Введите начальную дату (ДД.ММ.ГГГГ):"
    REPORT_ASK_DATE_TO = "Введите конечную дату (ДД.ММ.ГГГГ):"
    REPORT_INVALID_DATE = "Неверный формат. Используйте ДД.ММ.ГГГГ."
    REPORT_EMPTY = "За указанный период данных нет."
    REPORT_READY = "Отчёт готов."
    REPORT_ERROR = "Не удалось сформировать отчёт, попробуйте позже."

    MY_TASKS_TITLE = "Мои задачи"
    MY_TASKS_EMPTY = "У вас нет активных задач на сегодня."
    MY_TASKS_STARTED = "Задача взята в работу ✅"
    MY_TASKS_DONE = "Задача отмечена как выполненная ✅"
    MY_TASKS_NOT_FOUND = "Задача не найдена или уже недоступна."

class Buttons():

    @staticmethod
    def builder_org_types(org_types):
        builder = InlineKeyboardBuilder()
        for t in org_types:
            builder.row(
                CallbackButton(
                    text=t.org_type_name,
                    payload=f"org_type:{t.org_type_id}",
                )
            )
        return builder

    def build_main_menu(id_role: int) -> InlineKeyboardBuilder:
        builder = InlineKeyboardBuilder()

        # Базовые для всех
        # builder.row(CallbackButton(text="Моя организация", payload="my_org"))
        # builder.row(CallbackButton(text="Моя должность", payload="my_role"))
        # builder.row(CallbackButton(text="Коллеги", payload="colleagues"))
        builder.row(CallbackButton(text="Мои задачи", payload="my_tasks"))
        if id_role == ROLE_EMPLOYEE:
            builder.row(CallbackButton(text="Свободные задачи", payload="task_pool"))
        builder.row(CallbackButton(text="Объявления", payload="announcements"))

        # if id_role == ROLE_EMPLOYEE:
        #

        # Админ + руководитель
        if id_role in (ROLE_OWNER, ROLE_ADMIN):
            builder.row(CallbackButton(text="Управление сотрудниками", payload="manage_staff"))
            builder.row(CallbackButton(text="Управление объявлениями", payload="management_announcement"))
            builder.row(CallbackButton(text="Управление задачами", payload="manage_tasks"))
            builder.row(CallbackButton(text="Выгрузка отчетности", payload="get_statistiks"))

        if id_role == ROLE_ADMIN:
            builder.row(CallbackButton(text="О организации", payload="org_informations"))

        if id_role == ROLE_OWNER:
            builder.row(CallbackButton(text="Настройки организации", payload="org_settings"))

        builder.row(CallbackButton(text="Профиль", payload="profile"))
        builder.row(CallbackButton(text="Выйти из организации", payload="exit"))

        return builder


    builder_please_phone = InlineKeyboardBuilder()
    builder_please_phone.row(
        RequestContactButton(text="Поделиться номером")
    )

    builder_menu = InlineKeyboardBuilder()
    builder_menu.row(
        CallbackButton(text="Перейти в меню", payload="start_menu")
    )

    employee_new_organ = InlineKeyboardBuilder()
    employee_new_organ.row(
            CallbackButton(text="Присоединиться", payload="start_employees"),
            CallbackButton(text="Создать организацию", payload="new_organization"),
    )

    builder_profile = InlineKeyboardBuilder()
    builder_profile.row(
        CallbackButton(text="Изменить имя", payload="profile_edit_name")
    )
    builder_profile.row(
        CallbackButton(text="Изменить фамилию", payload="profile_edit_last_name")
    )
    builder_profile.row(
        CallbackButton(text="Изменить телефон", payload="profile_edit_phone")
    )
    builder_profile.row(
        CallbackButton(text="← Назад", payload="start_menu")
    )

    builder_manage_announcements = InlineKeyboardBuilder()
    builder_manage_announcements.row(
        CallbackButton(text="Создать объявление", payload="announcement_create")
    )
    builder_manage_announcements.row(
        CallbackButton(text="Мои объявления", payload="announcement_my_list")
    )
    builder_manage_announcements.row(
        CallbackButton(text="Назад", payload="start_menu")
    )

    # Кому адресовать
    builder_announcement_target = InlineKeyboardBuilder()
    builder_announcement_target.row(
        CallbackButton(text="Всем сотрудникам", payload="announcement_target_all")
    )
    builder_announcement_target.row(
        CallbackButton(text="Конкретным", payload="announcement_target_users")
    )
    builder_announcement_target.row(
        CallbackButton(text="Назад", payload="management_announcement")
    )

    # Кнопка «Готово» для выбора сотрудников
    builder_announcement_done = InlineKeyboardBuilder()
    builder_announcement_done.row(
        CallbackButton(text="Готово", payload="announcement_users_done")
    )

    builder_back = InlineKeyboardBuilder()
    builder_back.row(
        CallbackButton(text="Назад", payload="start_menu")
    )

    builder_org_settings = InlineKeyboardBuilder()
    builder_org_settings.row(
        CallbackButton(text="Название", payload="org_edit_name")
    )
    builder_org_settings.row(
        CallbackButton(text="Город", payload="org_edit_city")
    )
    builder_org_settings.row(
        CallbackButton(text="Тип", payload="org_edit_type")
    )
    builder_org_settings.row(
        CallbackButton(text="← Назад", payload="start_menu")
    )


    builder_announcements = InlineKeyboardBuilder()
    builder_announcements.row(
        CallbackButton(text="Новые (непрочитанные)", payload="ann_list_unread")
    )
    builder_announcements.row(
        CallbackButton(text="Созданные сегодня", payload="ann_list_today")
    )
    builder_announcements.row(
        CallbackButton(text="Поиск", payload="ann_search")
    )
    builder_announcements.row(
        CallbackButton(text="← Назад", payload="start_menu")
    )

    # Меню поиска
    builder_ann_search = InlineKeyboardBuilder()
    builder_ann_search.row(
        CallbackButton(text="По названию", payload="ann_search_by_title")
    )
    builder_ann_search.row(
        CallbackButton(text="По дате", payload="ann_search_by_date")
    )
    builder_ann_search.row(
        CallbackButton(text="Назад", payload="announcements")
    )

    builder_manage_staff = InlineKeyboardBuilder()
    builder_manage_staff.row(
        CallbackButton(text="Список сотрудников", payload="staff_list")
    )
    builder_manage_staff.row(
        CallbackButton(text="Назад", payload="start_menu")
    )

    # Меню управления сотрудниками
    builder_manage_staff = InlineKeyboardBuilder()
    builder_manage_staff.row(
        CallbackButton(text="Уволить", payload="staff_action_fire")
    )
    builder_manage_staff.row(
        CallbackButton(text="Изменить системную роль", payload="staff_action_role")
    )
    builder_manage_staff.row(
        CallbackButton(text="Изменить роль в организации", payload="staff_action_name_role")
    )
    builder_manage_staff.row(
        CallbackButton(text="← Назад", payload="start_menu")
    )

    # Системные роли для назначения
    builder_staff_roles = InlineKeyboardBuilder()
    builder_staff_roles.row(CallbackButton(text="Владелец", payload="staff_set_role:1"))
    builder_staff_roles.row(CallbackButton(text="Администратор", payload="staff_set_role:2"))
    builder_staff_roles.row(CallbackButton(text="Сотрудник", payload="staff_set_role:3"))
    builder_staff_roles.row(CallbackButton(text="Отмена", payload="staff_cancel"))

    # Подтверждение действия
    @staticmethod
    def builder_staff_confirm(action: str, member_id: int) -> InlineKeyboardBuilder:
        """
        action: 'fire' | 'role' | 'name_role'
        """
        b = InlineKeyboardBuilder()
        b.row(CallbackButton(
            text="Да, подтверждаю",
            payload=f"staff_confirm:{action}:{member_id}",
        ))
        b.row(CallbackButton(text="← Отмена", payload="staff_cancel"))
        return b

    # Меню «Управление задачами»
    builder_manage_tasks = InlineKeyboardBuilder()
    builder_manage_tasks.row(
        CallbackButton(text="Создать задачу", payload="task_create")
    )
    builder_manage_tasks.row(
        CallbackButton(text="Активные (кто что делает)", payload="task_active")
    )
    builder_manage_tasks.row(
        CallbackButton(text="Свободные с дедлайном", payload="task_pool")
    )
    builder_manage_tasks.row(
        CallbackButton(text="Редактировать", payload="task_edit")
    )
    builder_manage_tasks.row(
        CallbackButton(text="← Назад", payload="start_menu")
    )

    # Кому назначить
    builder_task_assignee = InlineKeyboardBuilder()
    builder_task_assignee.row(CallbackButton(text="Конкретному сотруднику", payload="task_assignee_user"))
    # builder_task_assignee.row(CallbackButton(text="🛠️ Роли", payload="task_assignee_role"))
    builder_task_assignee.row(CallbackButton(text=" В пул (свободная)", payload="task_assignee_pool"))
    builder_task_assignee.row(CallbackButton(text="← Отмена", payload="task_cancel"))

    builder_reports = InlineKeyboardBuilder()
    builder_reports.row(CallbackButton(text="Сотрудники", payload="report_employees"))
    # builder_reports.row(CallbackButton(text="Объявления", payload="report_announcements"))
    builder_reports.row(CallbackButton(text="Задачи", payload="report_tasks"))
    builder_reports.row(CallbackButton(text="Выполнение задач", payload="report_task_completion"))
    builder_reports.row(CallbackButton(text="← Назад", payload="start_menu"))

    # Что редактировать
    builder_task_edit_field = InlineKeyboardBuilder()
    builder_task_edit_field.row(CallbackButton(text="Название", payload="task_edit_title"))
    builder_task_edit_field.row(CallbackButton(text="Описание", payload="task_edit_desc"))
    builder_task_edit_field.row(CallbackButton(text="Вес", payload="task_edit_weight"))
    builder_task_edit_field.row(CallbackButton(text="Время, мин", payload="task_edit_minutes"))
    builder_task_edit_field.row(CallbackButton(text="← Отмена", payload="task_cancel"))

    @staticmethod
    def builder_task_pool(numbers: list, back_payload: str = "manage_tasks") -> InlineKeyboardBuilder:
        """numbers: список номеров задач в пуле"""
        b = InlineKeyboardBuilder()
        for n in numbers:
            b.row(CallbackButton(text=f"Взять задачу №{n}", payload=f"task_take:{n}"))
        b.row(CallbackButton(text="← Назад", payload=back_payload))
        return b

    builder_task_assignee = InlineKeyboardBuilder()
    builder_task_assignee.row(CallbackButton(text="Сотруднику", payload="task_assignee_user"))
    builder_task_assignee.row(CallbackButton(text="По роли в организации", payload="task_assignee_role"))
    builder_task_assignee.row(CallbackButton(text="Открытая (в пул)", payload="task_assignee_pool"))
    builder_task_assignee.row(CallbackButton(text="← Отмена", payload="task_cancel"))

    builder_task_recurrence = InlineKeyboardBuilder()
    builder_task_recurrence.row(CallbackButton(text="По расписанию", payload="task_recurrence_regular"))
    builder_task_recurrence.row(CallbackButton(text="Разовая", payload="task_recurrence_onetime"))
    builder_task_recurrence.row(CallbackButton(text="← Отмена", payload="task_cancel"))

    builder_task_yes_no = InlineKeyboardBuilder()
    builder_task_yes_no.row(CallbackButton(text="Да", payload="task_yes"))
    builder_task_yes_no.row(CallbackButton(text="Нет", payload="task_no"))
    builder_task_yes_no.row(CallbackButton(text="← Отмена", payload="task_cancel"))

    builder_task_period = InlineKeyboardBuilder()
    builder_task_period.row(CallbackButton(text="Указать даты", payload="task_period_dates"))
    builder_task_period.row(CallbackButton(text="Бессрочно", payload="task_period_infinite"))
    builder_task_period.row(CallbackButton(text="← Отмена", payload="task_cancel"))

    @staticmethod
    def builder_task_weekdays(selected: set) -> InlineKeyboardBuilder:
        b = InlineKeyboardBuilder()
        days = [("Пн", 1), ("Вт", 2), ("Ср", 4), ("Чт", 8), ("Пт", 16), ("Сб", 32), ("Вс", 64)]
        row = []
        for name, bit in days:
            mark = "✅" if bit in selected else "☐"
            row.append(CallbackButton(text=f"{mark} {name}", payload=f"task_wd_toggle:{bit}"))
        # по 4 в ряд
        b.row(*row[:4])
        b.row(*row[4:])
        b.row(CallbackButton(text="Готово", payload="task_wd_done"))
        b.row(CallbackButton(text="← Отмена", payload="task_cancel"))
        return b

    builder_task_weight = InlineKeyboardBuilder()
    for w in range(1, 11):
        builder_task_weight.row(CallbackButton(text=str(w), payload=f"task_weight:{w}"))
    builder_task_weight.row(CallbackButton(text="← Отмена", payload="task_cancel"))

    builder_task_confirm = InlineKeyboardBuilder()
    builder_task_confirm.row(CallbackButton(text="Создать", payload="task_confirm_create"))
    builder_task_confirm.row(CallbackButton(text="Изменить", payload="task_confirm_edit"))
    builder_task_confirm.row(CallbackButton(text="← Отмена", payload="task_cancel"))

    # # Системные роли для назначения
    # builder_staff_roles = InlineKeyboardBuilder()
    # builder_staff_roles.row(
    #     CallbackButton(text="👑 Владелец", payload="staff_set_role:1")
    # )
    # builder_staff_roles.row(
    #     CallbackButton(text="🛠️ Администратор", payload="staff_set_role:2")
    # )
    # builder_staff_roles.row(
    #     CallbackButton(text="👤 Сотрудник", payload="staff_set_role:3")
    # )
    # builder_staff_roles.row(
    #     CallbackButton(text="← Назад", payload="staff_list")
    # )
    #
    # # Действия над конкретным сотрудником
    # @staticmethod
    # def builder_staff_member(member_id: int) -> InlineKeyboardBuilder:
    #     b = InlineKeyboardBuilder()
    #     b.row(CallbackButton(
    #         text="🔁 Изменить системную роль",
    #         payload=f"staff_change_role:{member_id}",
    #     ))
    #     b.row(CallbackButton(
    #         text="🏷️ Изменить роль в организации",
    #         payload=f"staff_change_name_role:{member_id}",
    #     ))
    #     b.row(CallbackButton(
    #         text="❌ Уволить",
    #         payload=f"staff_fire:{member_id}",
    #     ))
    #     b.row(CallbackButton(
    #         text="← Назад",
    #         payload="staff_list",
    #     ))
    #     return b

    def builder_announcement_read(announcement_id: int) -> InlineKeyboardBuilder:
        b = InlineKeyboardBuilder()
        b.row(CallbackButton(
            text="✅ Прочитано",
            payload=f"announcement_read:{announcement_id}",
        ))
        return b

    @staticmethod
    def builder_ann_my_day(date_str: str, announcements: list) -> InlineKeyboardBuilder:
        """
        Кнопки: по одной на объявление + навигация по дням.
        date_str — 'YYYY-MM-DD'
        announcements — список Announcement
        """
        b = InlineKeyboardBuilder()
        for a in announcements:
            title = (a.title or "—")[:40]
            b.row(CallbackButton(
                text=f"📢 {title}",
                payload=f"ann_my_view:{a.announcement_id}",
            ))
        # Навигация по датам
        b.row(CallbackButton(text="День назад", payload=f"ann_my_shift:{date_str}:-1"))
        b.row(CallbackButton(text="Другая дата", payload=f"ann_my_pick_date:{date_str}"))
        b.row(CallbackButton(text="День вперёд", payload=f"ann_my_shift:{date_str}:+1"))
        b.row(CallbackButton(text="← Назад", payload="management_announcement"))
        return b

    @staticmethod
    def builder_ann_my_view(announcement_id: int, date_str: str) -> InlineKeyboardBuilder:
        b = InlineKeyboardBuilder()
        b.row(CallbackButton(
            text="Кто прочитал",
            payload=f"ann_my_readers:{announcement_id}:{date_str}",
        ))
        b.row(CallbackButton(
            text="Кто не прочитал",
            payload=f"ann_my_unreaders:{announcement_id}:{date_str}",
        ))
        b.row(CallbackButton(
            text="← К списку",
            payload=f"ann_my_day:{date_str}",
        ))
        return b

    @staticmethod
    def builder_my_tasks_list(items: list) -> InlineKeyboardBuilder:
        """
        items: список dict с полями:
          number, instance_id, title, planned_end, status
        По одной кнопке на задачу + назад.
        """
        b = InlineKeyboardBuilder()
        for it in items:

            b.row(CallbackButton(
                text=f"📌 {it['number']}. {it['title'][:40]}",
                payload=f"my_task_view:{it['instance_id']}",
            ))
        b.row(CallbackButton(text="← Назад", payload="start_menu"))
        return b

    @staticmethod
    def builder_my_task_actions(instance_id: int, can_start: bool, can_finish: bool) -> InlineKeyboardBuilder:
        b = InlineKeyboardBuilder()
        if can_start:
            b.row(CallbackButton(
                text="▶️ Начать выполнение",
                payload=f"my_task_start:{instance_id}",
            ))
        if can_finish:
            b.row(CallbackButton(
                text="✅ Отметить выполненной",
                payload=f"my_task_finish:{instance_id}",
            ))
        b.row(CallbackButton(
            text="📄 Подробнее",
            payload=f"my_task_details:{instance_id}",
        ))
        b.row(CallbackButton(text="← Назад", payload="my_tasks"))
        return b