import io
import os
import tempfile
from datetime import date

import aiohttp
from aiohttp import TCPConnector
from maxapi import Router, F
from maxapi.filters.command import CommandStart
from maxapi.types import BotStarted, BotStopped, MessageCreated, MessageCallback, CallbackButton, InputMediaBuffer
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from sqlalchemy.connectors import asyncio

from bot.ManagerTextAndButton import Texts, Buttons
from bot.StepsManage import *
from db_instance import db
from mailing.queue import enqueue_announcement
from models import Member, Role, Organization, ROLE_OWNER, ROLE_ADMIN
from reports import export_task_completion, export_tasks, export_employees, export_announcements
from reports.csv_export import _deliver_csv_as_text
from services import *
import logging

router = Router()

import io
import logging

from bot.instance import bot, BOT_TOKEN       # ← из нового модуля instance, а не dispatcher
from reports import (
    export_employees, export_announcements,
    export_tasks, export_task_completion,
)
from asyncio import sleep



MAX_API_BASE = "https://platform-api2.max.ru"


async def _send_report(event, exporter_func, filename: str, caption: str):
    user_id = event.from_user.user_id

    # 1. Права + генерация CSV
    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0):
            await event.message.answer("Вы не состоите в организации.")
            return
        if info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
            await event.message.answer("Недостаточно полномочий для выполнения операции.")
            return

        try:
            csv_bytes = exporter_func(session, info["org_id"])
        except Exception as e:
            logging.exception("Report error: %s", e)
            await event.message.answer("Не удалось сформировать отчёт.")
            return

    if isinstance(csv_bytes, str):
        csv_bytes = csv_bytes.encode("utf-8-sig")
    if not csv_bytes:
        await event.message.answer("За указанный период данные отсутствуют.")
        return

    # 2. Формируем медиа-объект из буфера (в памяти, без временных файлов)
    media = InputMediaBuffer(buffer=csv_bytes, filename=filename)

    # 3. Отправляем сообщение. maxapi сам загрузит файл и подставит вложение.
    try:
        await bot.send_message(
            user_id=user_id,
            text=caption,
            attachments=[media],
        )
        return
    except Exception as e:
        logging.warning("Отправка файла не удалась: %s", e)

    # 4. Fallback — текстом
    text = bytes(csv_bytes).decode("utf-8-sig")
    max_len = 3500
    truncated = len(text) > max_len
    if truncated:
        text = text[:max_len]

    body = f"{filename}\n```\n{text}\n```"
    if truncated:
        body += "\nОтображён фрагмент файла."
    await event.message.answer(body)

async def create_org_with_type(event, user_id, org_type_id):
    data = get_data(user_id)

    with db.session() as session:
        user = get_user_by_max_id(session, user_id)
        if user is None:
            await event.message.answer("Для продолжения необходимо пройти регистрацию: /start.")
            return

        org = create_organization(
            session,
            org_name=data.get("name_org"),
            city=data.get("org_city"),
            org_type_id=org_type_id,
        )
        create_member(
            session,
            user_id=user.user_id,
            role_id=ROLE_OWNER,
            organization_id=org.organization_id,
        )

        org_name = org.org_name
        code = get_org_code(session, org.organization_id)

    clear_state(user_id)
    set_step(user_id, Steps.DONE)

    await event.message.answer(
        f"Организация «{org_name}» создана!\n"
        f"Код для приглашения сотрудников: {code}",
        attachments=[Buttons.builder_menu.as_markup()],
    )

def build_staff_list_text(rows) -> str:
    """
    rows: список кортежей (Member, User, Role)
    Возвращает нумерованный текст.
    """
    lines = [Texts.STAFF_LIST_HEADER]
    for i, (member, user, role) in enumerate(rows, start=1):
        name = f"{user.user_name or ''} {user.last_name or ''}".strip() or f"user#{user.user_id}"
        sys_role = role.role_name or "—"
        org_role = member.name_org_role or "—"
        lines.append(f"{i}. {name} — {sys_role} / {org_role}")
    return "\n".join(lines)

@router.bot_started()
async def bot_started(event: BotStarted):
    user_id = event.from_user.user_id

    with db.session() as session:
        answer = check_work(session, user_id)

    # 1. Новый пользователь
    if answer == -1:
        set_step(user_id, Steps.WAITING_NAME)
        await event.bot.send_message(
            chat_id=event.chat_id,
            text=Texts.INTRO_TEXT,
        )
        return

    # 2. Без организации
    if answer == 0:
        await event.bot.send_message(
            chat_id=event.chat_id,
            text=(
                "Вы пока не состоите ни в одной организации.\n"
                "Создайте свою организацию или устройтесь в существующую."
            ),
            attachments=[Buttons.employee_new_organ.as_markup()],
        )
        return

    # 3. Есть организация — достаём поля из словаря
    role_name = answer["role_name"]
    org_name  = answer["org_name"]
    city      = answer["city"]
    role_id   = answer["role_id"]

    await event.bot.send_message(
        chat_id=event.chat_id,
        text=(
            f"Вы работаете в организации «{org_name}» ({city})\n"
            f"Ваша должность: {role_name}"
        ),
        attachments=[Buttons.build_main_menu(role_id).as_markup()],
    )

@router.message_created(CommandStart())
async def cmd_start(event: MessageCreated):
    user_id = event.from_user.user_id

    with db.session() as session:
        answer = check_work(session, user_id)

    # 1. Новый пользователь
    if answer == -1:
        set_step(user_id, Steps.WAITING_NAME)
        await event.message.answer(Texts.INTRO_TEXT)
        return

    # 2. Без организации
    if answer == 0:
        await event.message.answer(
            "Вы пока не состоите ни в одной организации.\n"
            "Создайте свою организацию или устройтесь в существующую.",
            attachments=[Buttons.employee_new_organ.as_markup()],
        )
        return

    # 3. Есть организация
    role_name = answer["role_name"]
    org_name  = answer["org_name"]
    city      = answer["city"]
    role_id   = answer["role_id"]

    await event.message.answer(
        f"Вы работаете в организации «{org_name}» ({city})\n"
        f"Ваша должность: {role_name}",
        attachments=[Buttons.build_main_menu(role_id).as_markup()],
    )


@router.message_created(F.message.body.text)
async def step_handler(event: MessageCreated):
    user_id = event.from_user.user_id
    text = event.message.body.text.strip()
    step = get_step(user_id)

    if step == Steps.WAITING_NAME:
        update_data(user_id, name=text)
        set_step(user_id, Steps.WAITING_LAST_NAME)
        await event.message.answer(Texts.ASK_LAST_NAME)
        return

    if step == Steps.WAITING_LAST_NAME:
        update_data(user_id, last_name=text)
        set_step(user_id, Steps.WAITING_PHONE)
        await event.message.answer(
            text=Texts.ASK_PHONE,
            attachments=[Buttons.builder_please_phone.as_markup()],
        )
        return

    if step == Steps.WAITING_NAME_ORG:
        update_data(user_id, name_org=text)
        set_step(user_id, Steps.WAITING_ORG_CITY)
        await event.message.answer(
            text=Texts.WAITING_ORG_CITY
        )
        return

    if step == Steps.WAITING_ORG_CITY:
        update_data(user_id, org_city=text)
        set_step(user_id, Steps.WAITING_ORG_TYPE)
        with db.session() as session:
            org_types = get_all_org_types(session)

        if not org_types:
            await event.message.answer(
                "Типы организаций ещё не настроены. Обратитесь к администратору."
            )
            return

        set_step(user_id, Steps.WAITING_ORG_TYPE)
        await event.message.answer(
            text="Выберите тип организации:",
            attachments=[Buttons.builder_org_types(org_types).as_markup()],
        )
        return

    if step == Steps.WAITING_ORG_CODE:
        code = text.strip()

        with db.session() as session:
            # 1. Ищем организацию по коду
            org = get_organization_by_code(session, code)

            if org is None:
                await event.message.answer(
                    "Код не найден. Проверьте код и попробуйте ещё раз."
                )
                return

            # 2. Ищем пользователя
            user = get_user_by_max_id(session, user_id)
            if user is None:
                await event.message.answer(
                    "Для продолжения необходимо пройти регистрацию: /start."
                )
                clear_state(user_id)
                set_step(user_id, Steps.START)
                return

            # 3. Проверяем, не состоит ли уже в этой организации
            existing = (
                session.query(Member)
                .filter(
                    Member.user_id == user.user_id,
                    Member.organization_id == org.organization_id,
                )
                .first()
            )
            if existing:
                await event.message.answer(
                    f"Вы уже состоите в организации «{org.org_name}»."
                )
                clear_state(user_id)
                set_step(user_id, Steps.DONE)
                return

            # 4. Создаём запись в Member
            role = get_or_create_role(session, "Сотрудник")
            create_member(
                session,
                user_id=user.user_id,
                role_id=role.role_id,
                organization_id=org.organization_id,
            )

            org_name = org.org_name
            org_city = org.city or "—"
            role_name = role.role_name

        # 5. Выходим из состояния анкеты
        clear_state(user_id)
        set_step(user_id, Steps.DONE)

        await event.message.answer(
            f"Вы присоединились к организации «{org_name}» ({org_city}).\n"
            f"Ваша должность: {role_name}.", attachments=[Buttons.builder_menu.as_markup()]
        )
        return

    if step == Steps.PROFILE_WAITING_NAME:
        with db.session() as session:
            user = get_user_by_max_id(session, user_id)
            if user:
                user.user_name = text
                session.commit()
        clear_state(user_id)
        set_step(user_id, Steps.DONE)
        await event.message.answer(f"Имя изменено: {text}")
        await handle_profile(event)  # вернуть меню профиля
        return

        # ---- Профиль: фамилия ----
    if step == Steps.PROFILE_WAITING_LAST_NAME:
        with db.session() as session:
            user = get_user_by_max_id(session, user_id)
            if user:
                user.last_name = text
                session.commit()
        clear_state(user_id)
        set_step(user_id, Steps.DONE)
        await event.message.answer(f"Фамилия изменена: {text}")
        await handle_profile(event)
        return

        # ---- Профиль: телефон (введён текстом) ----
    if step == Steps.PROFILE_WAITING_PHONE:
        cleaned = (
            text.replace("+", "").replace("-", "")
            .replace(" ", "").replace("(", "").replace(")", "")
        )
        if not cleaned.isdigit():
            await event.message.answer("Номер телефона указан некорректно. Повторите ввод.")
            return

        with db.session() as session:
            user = get_user_by_max_id(session, user_id)
            if user:
                user.number_phone = text
                session.commit()
        clear_state(user_id)
        set_step(user_id, Steps.DONE)
        await event.message.answer(f"Номер телефона изменён: {text}")
        await handle_profile(event)
        return

    # --- Заголовок объявления ---
    if step == Steps.ANNOUNCEMENT_WAITING_TITLE:
        update_data(user_id, ann_title=text)
        set_step(user_id, Steps.ANNOUNCEMENT_WAITING_BODY)
        await event.message.answer(Texts.ANNOUNCEMENTS_ASK_BODY)
        return

    # --- Текст объявления ---
    if step == Steps.ANNOUNCEMENT_WAITING_BODY:
        update_data(user_id, ann_body=text)
        set_step(user_id, Steps.ANNOUNCEMENT_WAITING_TARGET)
        await event.message.answer(
            Texts.ANNOUNCEMENTS_ASK_TARGET,
            attachments=[Buttons.builder_announcement_target.as_markup()],
        )
        return

    if step == Steps.ORG_WAITING_NAME:
        if not text:
            await event.message.answer(Texts.ORG_NAME_INVALID)
            return

        with db.session() as session:
            info = check_work(session, user_id)
            if info not in (-1, 0) and info["role_id"] == ROLE_OWNER:
                update_org_name(session, info["org_id"], text)

        clear_state(user_id)
        set_step(user_id, Steps.DONE)
        await event.message.answer(Texts.ORG_UPDATED)
        await handle_org_settings(event)
        return

        # ---- Настройки: город ----
    if step == Steps.ORG_WAITING_CITY:
        with db.session() as session:
            info = check_work(session, user_id)
            if info not in (-1, 0) and info["role_id"] == ROLE_OWNER:
                update_org_city(session, info["org_id"], text)

        clear_state(user_id)
        set_step(user_id, Steps.DONE)
        await event.message.answer(Texts.ORG_UPDATED)
        await handle_org_settings(event)
        return

    if step == Steps.ANN_WAITING_SEARCH_TITLE:
        with db.session() as session:
            info = check_work(session, user_id)
            if info in (-1, 0):
                await event.message.answer("Вы не состоите в организации.")
                return

            anns = search_announcements_by_title(session, info["user_id"], text)

        clear_state(user_id)
        set_step(user_id, Steps.DONE)

        if not anns:
            await event.message.answer(Texts.ANN_NOT_FOUND)
            return

        for ann in anns:
            await event.message.answer(
                format_announcement(ann),
                attachments=[Buttons.builder_announcement_read(ann.announcement_id).as_markup()],
            )
        return

        # ---- Поиск по дате ----
    if step == Steps.ANN_WAITING_SEARCH_DATE:
        try:
            date_ = datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            await event.message.answer(Texts.ANN_SEARCH_INVALID_DATE)
            return

        with db.session() as session:
            info = check_work(session, user_id)
            if info in (-1, 0):
                await event.message.answer("Вы не состоите в организации.")
                return

            anns = search_announcements_by_date(session, info["user_id"], date_)

        clear_state(user_id)
        set_step(user_id, Steps.DONE)

        if not anns:
            await event.message.answer(Texts.ANN_NOT_FOUND)
            return

        for ann in anns:
            await event.message.answer(
                format_announcement(ann),
                attachments=[Buttons.builder_announcement_read(ann.announcement_id).as_markup()],
            )
        return

    if step == Steps.STAFF_WAITING_NAME_ORG_ROLE:
        data = get_data(user_id)
        member_id = data.get("staff_target_member_id")
        if member_id is None:
            await event.message.answer("Сотрудник не выбран.")
            clear_state(user_id)
            set_step(user_id, Steps.DONE)
            return

        with db.session() as session:
            info = check_work(session, user_id)
            if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
                await event.message.answer("Недостаточно полномочий для выполнения операции.")
                return

            target = get_member_by_id(session, member_id)
            if target is None or target.organization_id != info["org_id"]:
                await event.message.answer("Сотрудник не найден.")
                return

            set_member_name_org_role(session, member_id, text)

        clear_state(user_id)
        set_step(user_id, Steps.DONE)
        await event.message.answer(Texts.STAFF_NAME_ROLE_UPDATED, attachments=[Buttons.builder_menu.as_markup()])
        return

    if step == Steps.STAFF_WAITING_NUMBER_FIRE:
        await _handle_staff_number_input(
            event, user_id, text,
            action="fire",
            confirm_text="Исключить сотрудника «{fio}» из организации?",
        )
        return

    if step == Steps.STAFF_WAITING_NUMBER_ROLE:
        await _handle_staff_number_input(
            event, user_id, text,
            action="role",
            confirm_text="Изменить системную роль сотрудника «{fio}»?",
        )
        return

    if step == Steps.STAFF_WAITING_NUMBER_NAME_ROLE:
        await _handle_staff_number_input(
            event, user_id, text,
            action="name_role",
            confirm_text="Изменить должность сотрудника «{fio}» в организации?",
        )
        return

        # ---- Ввод названия роли в организации (после подтверждения) ----
    if step == Steps.STAFF_WAITING_NAME_ORG_ROLE:
        data = get_data(user_id)
        member_id = data.get("staff_target_member_id")
        if member_id is None:
            await event.message.answer("Сотрудник не выбран.")
            clear_state(user_id)
            set_step(user_id, Steps.DONE)
            return

        with db.session() as session:
            info = check_work(session, user_id)
            if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
                await event.message.answer("Недостаточно полномочий для выполнения операции.")
                return
            target = get_member_by_id(session, member_id)
            if target is None or target.organization_id != info["org_id"]:
                await event.message.answer("Сотрудник не найден.")
                return
            set_member_name_org_role(session, member_id, text)

        clear_state(user_id)
        set_step(user_id, Steps.DONE)
        await event.message.answer(Texts.STAFF_NAME_ROLE_UPDATED, attachments=[Buttons.builder_menu.as_markup()])
        return

    if step == Steps.TASK_CREATE_TITLE:
        update_data(user_id, task_title=text)
        set_step(user_id, Steps.TASK_CREATE_DESC)
        await event.message.answer(Texts.TASKS_CREATE_DESC)
        return

    if step == Steps.TASK_CREATE_DESC:
        update_data(user_id, task_desc=None if text == "-" else text)
        set_step(user_id, Steps.TASK_CREATE_WEIGHT)
        await event.message.answer(Texts.TASKS_CREATE_WEIGHT)
        return

    if step == Steps.TASK_CREATE_WEIGHT:
        if not text.isdigit() or not (1 <= int(text) <= 10):
            await event.message.answer("Введите целое число от 1 до 10.")
            return
        update_data(user_id, task_weight=int(text))
        set_step(user_id, Steps.TASK_CREATE_MINUTES)
        await event.message.answer(Texts.TASKS_CREATE_MINUTES)
        return

    if step == Steps.TASK_CREATE_MINUTES:
        if not text.isdigit() or int(text) <= 0:
            await event.message.answer("Введите положительное целое число.")
            return
        update_data(user_id, task_minutes=int(text))

        # Создаём задачу в БД
        data = get_data(user_id)
        with db.session() as session:
            info = check_work(session, user_id)
            if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
                await event.message.answer("Недостаточно полномочий для выполнения операции.")
                return

            create_task(
                session,
                org_id=info["org_id"],
                title=data.get("task_title"),
                description=data.get("task_desc"),
                user_id=data.get("task_assignee_user_id"),
                weight=data.get("task_weight", 1),
                estimated_minutes=data.get("task_minutes", 60),
            )

        clear_state(user_id)
        set_step(user_id, Steps.DONE)
        await event.message.answer(Texts.TASKS_CREATED)
        return

    # --- выбор сотрудника для задачи ---
    if step == Steps.TASK_CREATE_ASSIGNEE_USER:
        if not text.isdigit():
            await event.message.answer("Введите целое число.")
            return
        index = get_data(user_id).get("task_user_index", {})
        user_id_target = index.get(int(text)) or index.get(str(text))
        if user_id_target is None:
            await event.message.answer("Указан неверный номер.")
            return
        update_data(user_id, task_assignee_user_id=user_id_target)
        set_step(user_id, Steps.TASK_CREATE_WEIGHT)
        await event.message.answer(Texts.TASKS_CREATE_WEIGHT)
        return

    # --- редактирование задачи ---
    if step == Steps.TASK_EDIT_NUMBER:
        if not text.isdigit():
            await event.message.answer(Texts.TASKS_BAD_NUMBER)
            return
        index = get_data(user_id).get("task_edit_index", {})
        task_id = index.get(int(text)) or index.get(str(text))
        if task_id is None:
            await event.message.answer(Texts.TASKS_BAD_NUMBER)
            return
        update_data(user_id, task_edit_id=task_id)
        await event.message.answer(
            Texts.TASKS_ASK_EDIT_FIELD,
            attachments=[Buttons.builder_task_edit_field.as_markup()],
        )
        set_step(user_id, Steps.DONE)  # выходим из шага, дальше — callback
        return

    if step == Steps.TASK_EDIT_TITLE:
        task_id = get_data(user_id).get("task_edit_id")
        with db.session() as session:
            update_task_field(session, task_id, "title", text)
        clear_state(user_id)
        set_step(user_id, Steps.DONE)
        await event.message.answer(Texts.TASKS_UPDATED)
        return

    if step == Steps.TASK_EDIT_DESC:
        task_id = get_data(user_id).get("task_edit_id")
        with db.session() as session:
            update_task_field(session, task_id, "description", text)
        clear_state(user_id)
        set_step(user_id, Steps.DONE)
        await event.message.answer(Texts.TASKS_UPDATED)
        return

    if step == Steps.TASK_EDIT_WEIGHT:
        if not text.isdigit() or not (1 <= int(text) <= 10):
            await event.message.answer("Введите целое число от 1 до 10.")
            return
        task_id = get_data(user_id).get("task_edit_id")
        with db.session() as session:
            update_task_field(session, task_id, "weight", int(text))
        clear_state(user_id)
        set_step(user_id, Steps.DONE)
        await event.message.answer(Texts.TASKS_UPDATED)
        return

    if step == Steps.TASK_EDIT_MINUTES:
        if not text.isdigit() or int(text) <= 0:
            await event.message.answer("Введите положительное целое число.")
            return
        task_id = get_data(user_id).get("task_edit_id")
        with db.session() as session:
            update_task_field(session, task_id, "estimated_minutes", int(text))
        clear_state(user_id)
        set_step(user_id, Steps.DONE)
        await event.message.answer(Texts.TASKS_UPDATED)
        return

    if step == Steps.TASK_TITLE:
        if not (3 <= len(text) <= 200):
            await event.message.answer(Texts.TASK_INVALID_TITLE)
            return
        _save(user_id, "title", text)
        set_step(user_id, Steps.TASK_DESCRIPTION)
        await event.message.answer(Texts.TASK_DESCRIPTION)
        return

        # === 2. Описание ===
    if step == Steps.TASK_DESCRIPTION:
        _save(user_id, "description", None if text == "-" else text)
        set_step(user_id, Steps.TASK_ASSIGNEE)
        await event.message.answer(
            Texts.TASK_ASSIGNEE,
            attachments=[Buttons.builder_task_assignee.as_markup()],
        )
        return

        # === 5A. Срок исполнения (разовая) ===
    if step == Steps.TASK_DEADLINE:
        try:
            dt = datetime.strptime(text, "%d.%m.%Y %H:%M")
        except ValueError:
            await event.message.answer(Texts.TASK_INVALID_DATETIME)
            return
        if dt <= datetime.now():
            await event.message.answer("Срок исполнения должен быть позднее текущего момента. Повторите ввод.")
            return
        _save(user_id, "planned_end", dt)
        set_step(user_id, Steps.TASK_START_TIME_ASK)
        await event.message.answer(
            Texts.TASK_START_TIME_ASK,
            attachments=[Buttons.builder_task_yes_no.as_markup()],
        )
        return

        # === 6A. Время начала (разовая, если «Да») ===
    if step == Steps.TASK_START_TIME:
        try:
            dt = datetime.strptime(text, "%d.%m.%Y %H:%M")
        except ValueError:
            await event.message.answer(Texts.TASK_INVALID_DATETIME)
            return
        planned_end = get_data(user_id).get("task_draft", {}).get("planned_end")
        if planned_end is not None and dt > planned_end:
            await event.message.answer("Время начала не может быть позднее срока исполнения. Повторите ввод.")
            return
        _save(user_id, "planned_start", dt)
        set_step(user_id, Steps.TASK_ESTIMATED_MINUTES)
        await event.message.answer(Texts.TASK_ESTIMATED_MINUTES)
        return

        # === 6B. Срок исполнения (постоянная, время суток) — обязателен ===
    if step == Steps.TASK_TIME:
        try:
            t = datetime.strptime(text, "%H:%M").time()
        except ValueError:
            await event.message.answer(Texts.TASK_INVALID_TIME)
            return
        _save(user_id, "time", t)
        # Как у разовой: после дедлайна спрашиваем необязательное время начала
        set_step(user_id, Steps.TASK_START_TIME_ASK)
        await event.message.answer(
            Texts.TASK_START_TIME_ASK,
            attachments=[Buttons.builder_task_yes_no.as_markup()],
        )
        return

        # === 7B. Время начала (постоянная, время суток, если «Да») ===
    if step == Steps.TASK_REGULAR_START_TIME:
        try:
            t = datetime.strptime(text, "%H:%M").time()
        except ValueError:
            await event.message.answer(Texts.TASK_INVALID_TIME)
            return
        deadline_t = get_data(user_id).get("task_draft", {}).get("time")
        if deadline_t is not None and t >= deadline_t:
            await event.message.answer(Texts.TASK_START_BEFORE_DEADLINE)
            return
        _save(user_id, "start_time", t)
        set_step(user_id, Steps.TASK_PERIOD_ASK)
        await event.message.answer(
            Texts.TASK_PERIOD_ASK,
            attachments=[Buttons.builder_task_period.as_markup()],
        )
        return

        # === 8B. Дата начала ===
    if step == Steps.TASK_PERIOD_START:
        try:
            d = datetime.strptime(text, "%d.%m.%Y").date()
        except ValueError:
            await event.message.answer(Texts.TASK_INVALID_DATE)
            return
        _save(user_id, "start_date", d)
        set_step(user_id, Steps.TASK_PERIOD_END)
        await event.message.answer(Texts.TASK_PERIOD_END)
        return

        # === 8B. Дата окончания ===
    if step == Steps.TASK_PERIOD_END:
        if text == "-":
            _save(user_id, "end_date", None)
        else:
            try:
                d = datetime.strptime(text, "%d.%m.%Y").date()
            except ValueError:
                await event.message.answer(Texts.TASK_INVALID_DATE)
                return
            _save(user_id, "end_date", d)
        set_step(user_id, Steps.TASK_ESTIMATED_MINUTES)
        await event.message.answer(Texts.TASK_ESTIMATED_MINUTES)
        return

        # === 7. EstimatedMinutes ===
    if step == Steps.TASK_ESTIMATED_MINUTES:
        if not text.isdigit() or int(text) <= 0:
            await event.message.answer(Texts.TASK_INVALID_INT)
            return
        _save(user_id, "estimated_minutes", int(text))
        set_step(user_id, Steps.TASK_WEIGHT)
        await event.message.answer(
            Texts.TASK_WEIGHT,
            attachments=[Buttons.builder_task_weight.as_markup()],
        )
        return

    if step == "task_assignee_user_number":
        if not text.isdigit():
            await event.message.answer(Texts.TASK_INVALID_INT)
            return
        idx = get_data(user_id).get("task_user_index", {})
        uid = idx.get(int(text)) or idx.get(str(text))
        if uid is None:
            await event.message.answer("Указан неверный номер.")
            return
        _save(user_id, "user_id", uid)
        set_step(user_id, Steps.TASK_RECURRENCE)
        await event.message.answer(
            Texts.TASK_RECURRENCE,
            attachments=[Buttons.builder_task_recurrence.as_markup()],
        )
        return

    if step == Steps.ANN_MY_WAITING_DATE:
        try:
            day = datetime.strptime(text, "%d.%m.%Y").date()
        except ValueError:
            await event.message.answer(Texts.ANN_MY_INVALID_DATE)
            return

        with db.session() as session:
            info = check_work(session, user_id)
            if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
                await event.message.answer("Недостаточно полномочий для выполнения операции.")
                return
            author_user_id = info["user_id"]

        clear_state(user_id)
        set_step(user_id, Steps.DONE)

        await _show_my_announcements(event, author_user_id, day)
        return

    if step == Steps.REPORT_WAITING_DATE_FROM:
        try:
            d_from = datetime.strptime(text, "%d.%m.%Y").date()
        except ValueError:
            await event.message.answer(Texts.REPORT_INVALID_DATE)
            return
        update_data(user_id, report_date_from=d_from.isoformat())
        set_step(user_id, Steps.REPORT_WAITING_DATE_TO)
        await event.message.answer(Texts.REPORT_ASK_DATE_TO)
        return

    if step == Steps.REPORT_WAITING_DATE_TO:
        try:
            d_to = datetime.strptime(text, "%d.%m.%Y").date()
        except ValueError:
            await event.message.answer(Texts.REPORT_INVALID_DATE)
            return

        data = get_data(user_id)
        from_str = data.get("report_date_from")
        if not from_str:
            clear_state(user_id)
            set_step(user_id, Steps.DONE)
            await event.message.answer(Texts.REPORT_ERROR)
            return

        d_from = datetime.strptime(from_str, "%Y-%m-%d").date()
        if d_to < d_from:
            await event.message.answer("Конечная дата не может быть ранее начальной.")
            return

        with db.session() as session:
            info = check_work(session, user_id)
            if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
                await event.message.answer("Недостаточно полномочий для выполнения операции.")
                return

            try:
                csv_bytes = export_announcements(session, info["org_id"], d_from, d_to)
            except Exception as e:
                logging.exception("Report announcements error: %s", e)
                await event.message.answer(Texts.REPORT_ERROR)
                clear_state(user_id)
                set_step(user_id, Steps.DONE)
                return

        clear_state(user_id)
        set_step(user_id, Steps.DONE)

        filename = f"announcements_{d_from.isoformat()}_{d_to.isoformat()}.csv"
        await _deliver_csv(event, csv_bytes, filename)
        return

    await event.message.answer("I don not know")

@router.message_created(F.message.body.attachments)
async def contact_handler(event: MessageCreated):
    user_id = event.from_user.user_id
    step = get_step(user_id)

    if step != Steps.WAITING_PHONE:
        return

    for attachment in event.message.body.attachments:
        if attachment.type == "contact":
            payload = attachment.payload

            phone = None
            if payload.vcf_info:
                for line in payload.vcf_info.splitlines():
                    if line.startswith("TEL"):
                        phone = line.split(":", 1)[-1].strip()
                        break

            if not phone:
                await event.message.answer("Не удалось получить номер телефона. Повторите попытку.")
                return

            # 1. Записываем телефон
            update_data(user_id, phone=phone)

            # 2. Забираем все данные ДО clear_state
            data = get_data(user_id)
            logging.info("Собранные данные: %s", data)

            # 3. Сохраняем в БД через корректную сессию
            with db.session() as session:
                get_or_create_user(
                    session,
                    max_id=user_id,
                    user_name=data.get("name"),
                    last_name=data.get("last_name"),
                    number_phone=data.get("phone"),
                )

            # 4. Только теперь чистим память
            clear_state(user_id)
            set_step(user_id, Steps.DONE)

            await event.message.answer(Texts.FINISH_TEXT, attachments=[Buttons.builder_menu.as_markup()])
            return



@router.message_callback(F.callback.payload == "start_employees")
async def handle_start_employees(event: MessageCallback):
    user_id = event.from_user.user_id
    set_step(user_id, Steps.WAITING_ORG_CODE)
    await event.message.answer(
        Texts.WAITING_COD_ORGANIZATION
    )



@router.message_callback(F.callback.payload == "new_organization")
async def handle_new_organization(event: MessageCallback):
    user_id=event.from_user.user_id
    set_step(user_id, Steps.WAITING_NAME_ORG)
    await event.bot.send_message(
        user_id=user_id,
        text=Texts.WAITING_NAME_COMPANI
    )

@router.message_callback(F.callback.payload.startswith("org_type:"))
async def handle_org_type(event: MessageCallback):
    user_id = event.from_user.user_id

    payload = event.callback.payload
    try:
        org_type_id = int(payload.split(":", 1)[1])
    except (IndexError, ValueError):
        await event.message.answer("Не удалось определить тип.")
        return

    step = get_step(user_id)

    if step == Steps.WAITING_ORG_TYPE:
        # --- Сценарий: создание организации ---
        await create_org_with_type(event, user_id, org_type_id)
        return

    if step == Steps.ORG_WAITING_TYPE:
        # --- Сценарий: редактирование типа ---
        with db.session() as session:
            info = check_work(session, user_id)
            if info in (-1, 0) or info["role_id"] != ROLE_OWNER:
                await event.message.answer("Недостаточно полномочий для выполнения операции.")
                return
            update_org_type(session, info["org_id"], org_type_id)

        clear_state(user_id)
        set_step(user_id, Steps.DONE)
        await event.message.answer("Тип организации изменён.")
        await handle_org_settings(event)
        return

    await event.message.answer("Выбранное действие не поддерживается.")
# @router.message_callback(F.callback.payload.startswith("org_type:"))
# async def handle_org_type(event: MessageCallback):
#     user_id = event.from_user.user_id
#
#     # Достаём org_type_id из payload
#     payload = event.callback.payload
#     try:
#         org_type_id = int(payload.split(":", 1)[1])
#     except (IndexError, ValueError):
#         await event.message.answer("Не удалось определить тип, попробуйте снова.")
#         return
#
#     data = get_data(user_id)
#
#     with db.session() as session:
#         user = get_user_by_max_id(session, user_id)
#         if user is None:
#             await event.message.answer("Для продолжения необходимо пройти регистрацию: /start.")
#             return
#
#         # Создаём организацию
#         org = create_organization(
#             session,
#             org_name=data.get("name_org"),
#             city=data.get("org_city"),
#             org_type_id=org_type_id,
#         )
#
#         # Привязываем пользователя
#         create_member(
#             session,
#             user_id=user.user_id,
#             role_id=ROLE_OWNER,
#             organization_id=org.organization_id,
#         )
#
#         # Сохраняем данные, которые нужны снаружи
#         org_name = org.org_name
#         code = get_org_code(session, org.organization_id)
#         role_id = ROLE_OWNER
#
#     # Чистим состояние
#     clear_state(user_id)
#     set_step(user_id, Steps.DONE)
#
#     # Одно сообщение — название, код и меню
#     await event.message.answer(
#         f"Организация «{org_name}» создана!\n"
#         f"Код для приглашения сотрудников: {code}",
#         attachments=[Buttons.builder_menu.as_markup()],
#     )

@router.message_callback(F.callback.payload.startswith("start_menu"))
async def handle_start_menu(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        user = get_user_by_max_id(session, user_id)
        if user is None:
            await event.message.answer("Вы не зарегистрированы. Для регистрации используйте команду /start.")
            return

        member = get_member_by_user_id(session, user.user_id)
        if member is None:
            await event.message.answer(
                "Вы не состоите ни в одной организации.",
                attachments=[Buttons.employee_new_organ.as_markup()],
            )
            return

        id_role = member.role_id

    await event.message.answer(
        "Функции:",
        attachments=[Buttons.build_main_menu(id_role).as_markup()],
    )

@router.message_callback(F.callback.payload.startswith("exit"))
async def handle_exit(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        user = get_user_by_max_id(session, user_id)
        if user is None:
            await event.message.answer("Вы не зарегистрированы. Для регистрации используйте команду /start.")
            return

        member = get_member_by_user_id(session, user.user_id)
        if member is None:
            await event.message.answer("Вы не состоите ни в одной организации.")
            return

        org = session.query(Organization).filter(
            Organization.organization_id == member.organization_id
        ).first()
        if org is None:
            await event.message.answer("Не удалось определить организацию.")
            return

        org_id = org.organization_id
        org_name = org.org_name
        role_id = member.role_id

        if role_id == ROLE_OWNER:
            member_count = count_org_members(session, org_id)

            if member_count > 1:
                await event.message.answer(
                    f"Вы — владелец организации «{org_name}».\n"
                    f"В организации ещё {member_count - 1} сотрудник(ов).\n"
                    f"Передайте права руководителя другому сотруднику "
                    f"или удалите организацию.",
                    attachments=[Buttons.builder_delete_org.as_markup()],
                )
                return

            delete_organization(session, org_id)
            await event.message.answer(
                f"Вы вышли из организации «{org_name}».\n"
                f"Так как вы были единственным участником, "
                f"организация удалена."
            )
        else:
            session.delete(member)
            session.commit()
            await event.message.answer(f"Вы вышли из состава организации «{org_name}».")

    clear_state(user_id)
    set_step(user_id, Steps.DONE)


@router.message_callback(F.callback.payload == "profile")
async def handle_profile(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        user = get_user_by_max_id(session, user_id)
        if user is None:
            await event.message.answer("Вы не зарегистрированы. Для регистрации используйте команду /start.")
            return

        name = user.user_name or "—"
        last_name = user.last_name or "—"
        phone = user.number_phone or "—"

    await event.message.answer(
        f"Ваш профиль\n\n"
        f"Имя: {name}\n"
        f"Фамилия: {last_name}\n"
        f"Телефон: {phone}",
        attachments=[Buttons.builder_profile.as_markup()],
    )

@router.message_callback(F.callback.payload == "profile_edit_name")
async def handle_profile_edit_name(event: MessageCallback):
    user_id = event.from_user.user_id
    set_step(user_id, Steps.PROFILE_WAITING_NAME)
    await event.message.answer(Texts.PROFILE_EDIT_NAME)

@router.message_callback(F.callback.payload == "profile_edit_last_name")
async def handle_profile_edit_last_name(event: MessageCallback):
    user_id = event.from_user.user_id
    set_step(user_id, Steps.PROFILE_WAITING_LAST_NAME)
    await event.message.answer(Texts.PROFILE_EDIT_LAST_NAME)

@router.message_callback(F.callback.payload == "profile_edit_phone")
async def handle_profile_edit_phone(event: MessageCallback):
    user_id = event.from_user.user_id
    set_step(user_id, Steps.PROFILE_WAITING_PHONE)
    await event.message.answer(
        Texts.PROFILE_EDIT_PHONE,
        attachments=[Buttons.builder_please_phone.as_markup()],
    )

@router.message_callback(F.callback.payload == "management_announcement")
async def handle_management_announcement(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        info = check_work(session, user_id)

    if info in (-1, 0):
        await event.message.answer("Необходимо пройти регистрацию и вступить в организацию.")
        return

    if info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
        await event.message.answer("Недостаточно полномочий для управления объявлениями.")
        return

    await event.message.answer(
        Texts.ANNOUNCEMENTS_TITLE,
        attachments=[Buttons.builder_manage_announcements.as_markup()],
    )

@router.message_callback(F.callback.payload == "announcement_create")
async def handle_announcement_create(event: MessageCallback):
    user_id = event.from_user.user_id
    set_step(user_id, Steps.ANNOUNCEMENT_WAITING_TITLE)
    await event.message.answer(Texts.ANNOUNCEMENTS_ASK_TITLE)

# @router.message_callback(F.callback.payload == "announcement_target_all")
# async def handle_announcement_target_all(event: MessageCallback):
#     user_id = event.from_user.user_id
#
#     with db.session() as session:
#         info = check_work(session, user_id)
#         if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
#             await event.message.answer("Недостаточно полномочий для выполнения операции.")
#             return
#
#         data = get_data(user_id)
#
#         members = get_all_org_members(session, info["org_id"])
#         target_ids = [m.user_id for m in members]
#
#         ann = create_announcement(
#             session,
#             org_id=info["org_id"],
#             author_user_id=info["user_id"],
#             title=data.get("ann_title"),
#             body=data.get("ann_body"),
#             target_user_ids=target_ids,
#         )
#         ann_id = ann.announcement_id
#
#     clear_state(user_id)
#     set_step(user_id, Steps.DONE)
#
#     # Рассылка — отдельно, после закрытия сессии
#     for uid in target_ids:
#         try:
#             await event.bot.send_message(
#                 user_id=uid,
#                 text=f"📢 {data.get('ann_title')}\n\n{data.get('ann_body')}",
#                 attachments=[Buttons.builder_announcement_read(ann_id).as_markup()],
#             )
#         except Exception as e:
#             logging.warning("Не доставлено %s: %s", uid, e)
#
#     await event.message.answer(Texts.ANNOUNCEMENTS_SAVED)

@router.message_callback(F.callback.payload == "announcement_target_all")
async def handle_announcement_target_all(event: MessageCallback):
    user_id = event.from_user.user_id

    # 1. Проверка прав (быстро, одна сессия)
    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
            await event.message.answer("Недостаточно полномочий для выполнения операции.")
            return

        data = get_data(user_id)
        members = get_all_org_members(session, info["org_id"])
        target_ids = [m.user_id for m in members]

        # 2. Создаём Announcement + AnnouncementRecipient (синхронный INSERT)
        ann = create_announcement(
            session,
            org_id=info["org_id"],
            author_user_id=info["user_id"],
            title=data.get("ann_title"),
            body=data.get("ann_body"),
            target_user_ids=target_ids,
        )
        ann_id = ann.announcement_id

    clear_state(user_id)
    set_step(user_id, Steps.DONE)

    # 3. Кладём в очередь — НЕ await!
    enqueue_announcement(ann_id)

    # 4. Сразу отвечаем админу
    await event.message.answer(
        f"Объявление поставлено в очередь "
        f"({len(target_ids)} получателей)."
    )

@router.message_callback(F.callback.payload == "announcement_target_users")
async def handle_announcement_target_users(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
            await event.message.answer("Недостаточно полномочий для выполнения операции.")
            return

        members = get_all_org_members(session, info["org_id"])
        # Строим список кнопок сотрудников
        builder = InlineKeyboardBuilder()
        for m in members:
            if m.user_id == info["user_id"]:
                continue
            builder.row(CallbackButton(
                text=f"[ ] {m.user_id}",   # позже замените на имя
                payload=f"announcement_pick:{m.user_id}",
            ))
        builder.row(CallbackButton(text="Готово", payload="announcement_users_done"))

    update_data(user_id, ann_selected=[])
    set_step(user_id, Steps.ANNOUNCEMENT_WAITING_USERS)
    await event.message.answer(
        Texts.ANNOUNCEMENTS_ASK_USERS,
        attachments=[builder.as_markup()],
    )

@router.message_callback(F.callback.payload.startswith("announcement_pick:"))
async def handle_announcement_pick(event: MessageCallback):
    user_id = event.from_user.user_id
    payload = event.callback.payload
    try:
        picked = int(payload.split(":", 1)[1])
    except (IndexError, ValueError):
        return

    selected = get_data(user_id).get("ann_selected", [])
    if picked in selected:
        selected.remove(picked)
    else:
        selected.append(picked)
    update_data(user_id, ann_selected=selected)

    # Не обязательно обновлять сообщение — можно просто ответить алертом
    await event.message.answer(f"Выбрано получателей: {len(selected)}")

@router.message_callback(F.callback.payload == "announcement_users_done")
async def handle_announcement_users_done(event: MessageCallback):
    user_id = event.from_user.user_id
    data = get_data(user_id)
    target_ids = data.get("ann_selected", [])

    if not target_ids:
        await event.message.answer("Получатели не выбраны.")
        return

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0):
            return

        ann = create_announcement(
            session,
            org_id=info["org_id"],
            author_user_id=info["user_id"],
            title=data.get("ann_title"),
            body=data.get("ann_body"),
            target_user_ids=target_ids,
        )
        ann_id = ann.announcement_id

    clear_state(user_id)
    set_step(user_id, Steps.DONE)

    for uid in target_ids:
        try:
            await event.bot.send_message(
                user_id=uid,
                text=f"{data.get('ann_title')}\n\n{data.get('ann_body')}",
                attachments=[Buttons.builder_announcement_read(ann_id).as_markup()],
            )
        except Exception as e:
            logging.warning("Не доставлено %s: %s", uid, e)

    await event.message.answer(Texts.ANNOUNCEMENTS_SAVED)

@router.message_callback(F.callback.payload.startswith("announcement_read:"))
async def handle_announcement_read(event: MessageCallback):
    user_id = event.from_user.user_id
    payload = event.callback.payload
    try:
        ann_id = int(payload.split(":", 1)[1])
    except (IndexError, ValueError):
        return

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0):
            return
        mark_announcement_read(session, ann_id, info["user_id"])

    await event.message.answer("Объявление отмечено как прочитанное.")

@router.message_callback(F.callback.payload == "org_informations")
async def handle_org_informations(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        info = check_work(session, user_id)

        if info == -1:
            await event.message.answer("Вы не зарегистрированы. Для регистрации используйте команду /start.")
            return
        if info == 0:
            await event.message.answer("Вы не состоите ни в одной организации.")
            return

        org_id = info["org_id"]

        org = get_org_info(session, org_id)
        members_stats = get_org_members_stats(session, org_id)

    # Код приглашения
    invite_code = encode_org_id(org_id)

    # Строки по ролям
    roles_lines = "\n".join(
        f"  • {r['role_name']}: {r['count']}"
        for r in members_stats
    ) or "  • нет сотрудников"

    text = (
        f"{org['org_name']}\n"
        f"Город: {org['city']}\n"
        f"Тип: {org['org_type_name']}\n"
        f"\n"
        f"Всего сотрудников: {org['members_count']}\n"
        f"{roles_lines}\n"
        f"\n"
        f"Код для приглашения сотрудников:\n"
        f"`{invite_code}`\n"
        f"\n"
        f"Передайте этот код новому сотруднику — он введёт его в боте, "
        f"чтобы присоединиться к организации."
    )

    await event.message.answer(
        text,
        attachments=[Buttons.builder_back.as_markup()],
    )

@router.message_callback(F.callback.payload == "org_settings")
async def handle_org_settings(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        info = check_work(session, user_id)

        if info in (-1, 0):
            await event.message.answer("Вы не состоите в организации.")
            return

        # Настройки доступны только владельцу
        if info["role_id"] != ROLE_OWNER:
            await event.message.answer("Изменение настроек доступно только владельцу организации.")
            return

        org = get_org_info(session, info["org_id"])

    invite_code = encode_org_id(info["org_id"])

    text = (
        f"Настройки организации\n\n"
        f"Название: {org['org_name']}\n"
        f"Город: {org['city']}\n"
        f"Тип: {org['org_type_name']}\n"
        f"\n"
        f"Код для приглашения сотрудников:\n"
        f"`{invite_code}`\n"
        f"\n"
        f"Передайте этот код новому сотруднику — он введёт его в боте."
    )

    await event.message.answer(
        text,
        attachments=[Buttons.builder_org_settings.as_markup()],
    )

@router.message_callback(F.callback.payload == "org_edit_name")
async def handle_org_edit_name(event: MessageCallback):
    user_id = event.from_user.user_id
    set_step(user_id, Steps.ORG_WAITING_NAME)
    await event.message.answer(Texts.ORG_EDIT_NAME)

@router.message_callback(F.callback.payload == "org_edit_city")
async def handle_org_edit_city(event: MessageCallback):
    user_id = event.from_user.user_id
    set_step(user_id, Steps.ORG_WAITING_CITY)
    await event.message.answer(Texts.ORG_EDIT_CITY)

@router.message_callback(F.callback.payload == "org_edit_type")
async def handle_org_edit_type(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0) or info["role_id"] != ROLE_OWNER:
            await event.message.answer("Недостаточно полномочий для выполнения операции.")
            return

        org_types = get_all_org_types(session)

    if not org_types:
        await event.message.answer("Типы организаций не заданы.")
        return

    set_step(user_id, Steps.ORG_WAITING_TYPE)
    await event.message.answer(
        Texts.ORG_EDIT_TYPE,
        attachments=[Buttons.builder_org_types(org_types).as_markup()],
    )

@router.message_callback(F.callback.payload.startswith("org_type_pick:"))
async def handle_org_type_pick(event: MessageCallback):
    user_id = event.from_user.user_id

    if get_step(user_id) != Steps.ORG_WAITING_TYPE:
        return   # не в сценарии редактирования — игнорируем

    payload = event.callback.payload
    try:
        org_type_id = int(payload.split(":", 1)[1])
    except (IndexError, ValueError):
        return

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0) or info["role_id"] != ROLE_OWNER:
            await event.message.answer("Недостаточно полномочий для выполнения операции.")
            return

        update_org_type(session, info["org_id"], org_type_id)

    clear_state(user_id)
    set_step(user_id, Steps.DONE)

    await event.message.answer(Texts.ORG_UPDATED)
    await handle_org_settings(event)   # возвращаем в меню настроек

@router.message_callback(F.callback.payload == "announcements")
async def handle_announcements(event: MessageCallback):
    await event.message.answer(
        Texts.ANN_TITLE,
        attachments=[Buttons.builder_announcements.as_markup()],
    )

def format_announcement(ann) -> str:
    created = ann.created_at.strftime("%d.%m.%Y %H:%M") if ann.created_at else "—"
    return (
        f"{ann.title or '—'}\n"
        f"{ann.body}\n"
        f"{created}"
    )


@router.message_callback(F.callback.payload == "ann_list_unread")
async def handle_ann_list_unread(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0):
            await event.message.answer("Вы не состоите в организации.")
            return

        anns = get_unread_announcements(session, info["user_id"])

    if not anns:
        await event.message.answer(Texts.ANN_EMPTY)
        return

    # Отправляем по одному с кнопкой «Прочитано»
    for ann in anns:
        await event.message.answer(
            format_announcement(ann),
            attachments=[Buttons.builder_announcement_read(ann.announcement_id).as_markup()],
        )

@router.message_callback(F.callback.payload == "ann_list_today")
async def handle_ann_list_today(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0):
            await event.message.answer("Вы не состоите в организации.")
            return

        anns = get_today_announcements(session, info["user_id"])

    if not anns:
        await event.message.answer("Сегодня объявления не публиковались.")
        return

    for ann in anns:
        # у сегодняшних тоже показываем кнопку «Прочитано»,
        # даже если они уже прочитаны — не критично
        await event.message.answer(
            format_announcement(ann),
            attachments=[Buttons.builder_announcement_read(ann.announcement_id).as_markup()],
        )

@router.message_callback(F.callback.payload == "ann_search")
async def handle_ann_search(event: MessageCallback):
    await event.message.answer(
        Texts.ANN_SEARCH_BY,
        attachments=[Buttons.builder_ann_search.as_markup()],
    )


@router.message_callback(F.callback.payload == "ann_search_by_title")
async def handle_ann_search_by_title(event: MessageCallback):
    user_id = event.from_user.user_id
    set_step(user_id, Steps.ANN_WAITING_SEARCH_TITLE)
    await event.message.answer(Texts.ANN_SEARCH_TITLE)


@router.message_callback(F.callback.payload == "ann_search_by_date")
async def handle_ann_search_by_date(event: MessageCallback):
    user_id = event.from_user.user_id
    set_step(user_id, Steps.ANN_WAITING_SEARCH_DATE)
    await event.message.answer(Texts.ANN_SEARCH_DATE)

@router.message_callback(F.callback.payload == "manage_staff")
async def handle_manage_staff(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0):
            await event.message.answer("Вы не состоите в организации.")
            return
        if info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
            await event.message.answer("Недостаточно полномочий для управления сотрудниками.")
            return

        rows = get_org_members_full(session, info["org_id"])

    if not rows:
        await event.message.answer(Texts.STAFF_EMPTY)
        return

    # Строим карту номер → member_id, сохраняем в состоянии
    number_to_member = {i: m.member_id for i, (m, _, _) in enumerate(rows, start=1)}
    update_data(user_id, staff_index=number_to_member)

    text = build_staff_list_text(rows)

    await event.message.answer(
        text,
        attachments=[Buttons.builder_manage_staff.as_markup()],
    )

@router.message_callback(F.callback.payload == "staff_action_fire")
async def handle_staff_action_fire(event: MessageCallback):
    user_id = event.from_user.user_id
    set_step(user_id, Steps.STAFF_WAITING_NUMBER_FIRE)
    await event.message.answer(Texts.STAFF_ASK_NUMBER_FIRE)

@router.message_callback(F.callback.payload == "staff_action_role")
async def handle_staff_action_role(event: MessageCallback):
    user_id = event.from_user.user_id
    set_step(user_id, Steps.STAFF_WAITING_NUMBER_ROLE)
    await event.message.answer(Texts.STAFF_ASK_NUMBER_ROLE)

@router.message_callback(F.callback.payload == "staff_action_name_role")
async def handle_staff_action_name_role(event: MessageCallback):
    user_id = event.from_user.user_id
    set_step(user_id, Steps.STAFF_WAITING_NUMBER_NAME_ROLE)
    await event.message.answer(Texts.STAFF_ASK_NUMBER_NAME_ROLE)

async def _handle_staff_number_input(event, user_id: int, text: str, action: str, confirm_text: str):
    """
    Разбирает введённый номер, находит member_id по staff_index,
    подтягивает ФИО и показывает подтверждение с именем (не номером).
    """
    if not text.isdigit():
        await event.message.answer(Texts.STAFF_BAD_NUMBER)
        return

    n = int(text)
    data = get_data(user_id)
    index = data.get("staff_index", {})

    # ключи могли стать строками — поддерживаем оба варианта
    member_id = index.get(n) or index.get(str(n))
    if member_id is None:
        await event.message.answer(Texts.STAFF_BAD_NUMBER)
        return

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
            await event.message.answer("Недостаточно полномочий для выполнения операции.")
            return

        target = get_member_by_id(session, member_id)
        if target is None or target.organization_id != info["org_id"]:
            await event.message.answer("Сотрудник не найден.")
            return

        # ---- защиты ----
        if action == "fire":
            if target.member_id == info["member_id"]:
                await event.message.answer(Texts.STAFF_CANNOT_FIRE_SELF)
                return
            if target.role_id == ROLE_OWNER:
                await event.message.answer(Texts.STAFF_CANNOT_FIRE_OWNER)
                return
            if info["role_id"] == ROLE_ADMIN and target.role_id == ROLE_ADMIN:
                await event.message.answer("Администратор не вправе исключать администраторов.")
                return

        if action in ("role", "name_role"):
            if info["role_id"] == ROLE_ADMIN and target.role_id in (ROLE_OWNER, ROLE_ADMIN):
                await event.message.answer(
                    "Администратор не вправе изменять роли владельца и администраторов."
                )
                return

        # ---- ФИО для подтверждения ----
        user = session.query(User).filter(User.user_id == target.user_id).first()
        fio = (
            f"{user.user_name or ''} {user.last_name or ''}".strip()
            or f"user#{target.user_id}"
        )

    update_data(user_id, staff_target_member_id=member_id)

    await event.message.answer(
        confirm_text.format(fio=fio),
        attachments=[Buttons.builder_staff_confirm(action, member_id).as_markup()],
    )

@router.message_callback(F.callback.payload.startswith("staff_confirm:"))
async def handle_staff_confirm(event: MessageCallback):
    user_id = event.from_user.user_id
    payload = event.callback.payload

    # staff_confirm:<action>:<member_id>
    parts = payload.split(":")
    if len(parts) != 3:
        return
    action, member_id_str = parts[1], parts[2]
    try:
        member_id = int(member_id_str)
    except ValueError:
        return

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
            await event.message.answer("Недостаточно полномочий для выполнения операции.")
            return

        target = get_member_by_id(session, member_id)
        if target is None or target.organization_id != info["org_id"]:
            await event.message.answer("Сотрудник не найден.")
            return

        # защита от self / owner / admin-admin
        if action == "fire":
            if target.member_id == info["member_id"]:
                await event.message.answer(Texts.STAFF_CANNOT_FIRE_SELF)
                return
            if target.role_id == ROLE_OWNER:
                await event.message.answer(Texts.STAFF_CANNOT_FIRE_OWNER)
                return
            if info["role_id"] == ROLE_ADMIN and target.role_id == ROLE_ADMIN:
                await event.message.answer("Администратор не вправе исключать администраторов.")
                return

            fire_member(session, member_id)
            clear_state(user_id)
            set_step(user_id, Steps.DONE)
            await event.message.answer(Texts.STAFF_FIRED,  attachments=[Buttons.builder_menu.as_markup()])
            return

        if action == "role":
            if info["role_id"] == ROLE_ADMIN and target.role_id in (ROLE_OWNER, ROLE_ADMIN):
                await event.message.answer("Администратор не вправе изменять роли владельца и администраторов.")
                return

            # запоминаем цель и просим выбрать роль
            update_data(user_id, staff_target_member_id=member_id)
            set_step(user_id, Steps.STAFF_WAITING_NUMBER_ROLE)   # остаёмся в контексте
            await event.message.answer(
                Texts.STAFF_ASK_NEW_ROLE,
                attachments=[Buttons.builder_staff_roles.as_markup()],
            )
            return

        if action == "name_role":
            if info["role_id"] == ROLE_ADMIN and target.role_id in (ROLE_OWNER, ROLE_ADMIN):
                await event.message.answer("Администратор не вправе изменять роли владельца и администраторов.")
                return

            update_data(user_id, staff_target_member_id=member_id)
            set_step(user_id, Steps.STAFF_WAITING_NAME_ORG_ROLE)
            await event.message.answer(Texts.STAFF_ASK_NAME_ORG_ROLE)
            return

@router.message_callback(F.callback.payload.startswith("staff_set_role:"))
async def handle_staff_set_role(event: MessageCallback):
    user_id = event.from_user.user_id
    try:
        new_role_id = int(event.callback.payload.split(":", 1)[1])
    except (IndexError, ValueError):
        return

    data = get_data(user_id)
    member_id = data.get("staff_target_member_id")
    if member_id is None:
        await event.message.answer("Сотрудник не выбран.")
        return

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
            await event.message.answer("Недостаточно полномочий для выполнения операции.")
            return

        if info["role_id"] == ROLE_ADMIN and new_role_id in (ROLE_OWNER, ROLE_ADMIN):
            await event.message.answer("Администратор не вправе назначать владельца и администраторов.")
            return

        target = get_member_by_id(session, member_id)
        if target is None or target.organization_id != info["org_id"]:
            await event.message.answer("Сотрудник не найден.")
            return

        if target.role_id == ROLE_OWNER and new_role_id != ROLE_OWNER:
            await event.message.answer("Понижение роли владельца не допускается.")
            return

        set_member_role(session, member_id, new_role_id)

    clear_state(user_id)
    set_step(user_id, Steps.DONE)
    await event.message.answer(Texts.STAFF_ROLE_UPDATED, attachments=[Buttons.builder_menu.as_markup()])

@router.message_callback(F.callback.payload == "staff_cancel")
async def handle_staff_cancel(event: MessageCallback):
    user_id = event.from_user.user_id
    clear_state(user_id)
    set_step(user_id, Steps.DONE)
    await event.message.answer("Действие отменено.")

@router.message_callback(F.callback.payload == "manage_tasks")
async def handle_manage_tasks(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        info = check_work(session, user_id)

    if info in (-1, 0):
        await event.message.answer("Вы не состоите в организации.")
        return
    if info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
        await event.message.answer("Недостаточно полномочий для управления задачами.")
        return

    await event.message.answer(
        Texts.TASKS_TITLE,
        attachments=[Buttons.builder_manage_tasks.as_markup()],
    )

@router.message_callback(F.callback.payload == "task_active")
async def handle_task_active(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
            await event.message.answer("Недостаточно полномочий для выполнения операции.")
            return

        items = get_active_instances(session, info["org_id"])

    if not items:
        await event.message.answer(Texts.TASKS_EMPTY_ACTIVE)
        return

    lines = []
    for it in items:
        deadline = it["planned_end"].strftime("%d.%m %H:%M") if it["planned_end"] else "—"
        lines.append(
            f"{it['assignee']}\n"
            f"   {it['title']}\n"
            f"   Срок: до {deadline}; вес: {it['weight']}"
        )
    await event.message.answer("Задачи в работе:\n\n" + "\n\n".join(lines))

@router.message_callback(F.callback.payload == "task_pool")
async def handle_task_pool(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0):
            await event.message.answer("Вы не состоите в организации.")
            return

        is_manager = info["role_id"] in (ROLE_OWNER, ROLE_ADMIN)
        # Владелец/админ видят весь пул, сотрудник — только назначенный ему
        items = get_pool_instances(
            session,
            info["org_id"],
            hours_ahead=48,
            member_id=None if is_manager else info["member_id"],
        )

    if not items:
        await event.message.answer(Texts.TASKS_EMPTY_POOL)
        return

    # Сохраняем карту номер → instance_id
    index = {it["number"]: it["instance_id"] for it in items}
    update_data(user_id, task_pool_index=index)

    lines = []
    for it in items:
        deadline = it["planned_end"].strftime("%d.%m %H:%M") if it["planned_end"] else "—"
        lines.append(
            f"{it['number']}. {it['title']}\n"
            f"   Срок: до {deadline}; вес: {it['weight']}"
        )

    await event.message.answer(
        "🆓 Свободные задачи:\n\n" + "\n\n".join(lines),
        attachments=[Buttons.builder_task_pool(
            [it["number"] for it in items],
            back_payload="manage_tasks" if is_manager else "start_menu",
        ).as_markup()],
    )

@router.message_callback(F.callback.payload.startswith("task_take:"))
async def handle_task_take(event: MessageCallback):
    user_id = event.from_user.user_id
    try:
        n = int(event.callback.payload.split(":", 1)[1])
    except (IndexError, ValueError):
        return

    data = get_data(user_id)
    index = data.get("task_pool_index", {})
    instance_id = index.get(n) or index.get(str(n))
    if instance_id is None:
        await event.message.answer(Texts.TASKS_BAD_NUMBER)
        return

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0):
            return
        ok = take_task_from_pool(session, instance_id, info["user_id"], org_id=info["org_id"])

    if ok:
        await event.message.answer(f"Задача №{n} принята в работу.")
    else:
        await event.message.answer("Не удалось принять задачу: она уже назначена другому сотруднику.")

@router.message_callback(F.callback.payload == "task_edit")
async def handle_task_edit(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
            await event.message.answer("Недостаточно полномочий для выполнения операции.")
            return

        rows = (
            session.query(Task)
            .filter(Task.organization_id == info["org_id"], Task.is_active == True)
            .order_by(Task.task_id)
            .all()
        )

    if not rows:
        await event.message.answer("Активные задачи отсутствуют.")
        return

    index = {i: t.task_id for i, t in enumerate(rows, start=1)}
    update_data(user_id, task_edit_index=index)

    lines = [f"{i}. {t.title}" for i, t in enumerate(rows, start=1)]
    set_step(user_id, Steps.TASK_EDIT_NUMBER)
    await event.message.answer(
        "Введите номер задачи для редактирования:\n" + "\n".join(lines),
    )


@router.message_callback(F.callback.payload.startswith("task_edit_"))
async def handle_task_edit_field(event: MessageCallback):
    user_id = event.from_user.user_id
    field = event.callback.payload.split("_", 2)[2]   # title | desc | weight | minutes
    mapping = {
        "title":   Steps.TASK_EDIT_TITLE,
        "desc":    Steps.TASK_EDIT_DESC,
        "weight":  Steps.TASK_EDIT_WEIGHT,
        "minutes": Steps.TASK_EDIT_MINUTES,
    }
    step = mapping.get(field)
    if step is None:
        return
    set_step(user_id, step)

    ask = {
        "title":   Texts.TASKS_ASK_NEW_TITLE,
        "desc":    Texts.TASKS_ASK_NEW_DESC,
        "weight":  Texts.TASKS_ASK_NEW_WEIGHT,
        "minutes": Texts.TASKS_ASK_NEW_MINUTES,
    }[field]
    await event.message.answer(ask)


@router.message_callback(F.callback.payload == "task_cancel")
async def handle_task_cancel(event: MessageCallback):
    user_id = event.from_user.user_id
    clear_state(user_id)
    set_step(user_id, Steps.DONE)
    await event.message.answer("Операция отменена.")

@router.message_callback(F.callback.payload == "task_assignee_role")
async def handle_task_assignee_role(event: MessageCallback):
    user_id = event.from_user.user_id
    set_step(user_id, Steps.TASK_ORG_ROLE_NAME)
    await event.message.answer(Texts.TASK_ORG_ROLE_NAME)

@router.message_callback(F.callback.payload == "task_confirm_create")
async def handle_task_confirm_create(event: MessageCallback):
    user_id = event.from_user.user_id
    d = get_data(user_id).get("task_draft", {})

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
            await event.message.answer("Недостаточно полномочий для выполнения операции.")
            return

        if d.get("is_regular"):
            task = create_regular_task(
                session,
                org_id=info["org_id"],
                title=d["title"],
                description=d.get("description"),
                user_id=d.get("user_id"),
                weekday_mask=d["weekday_mask"],
                time_=d["time"],
                start_date=d["start_date"],
                end_date=d.get("end_date"),
                start_time=d.get("start_time"),
                estimated_minutes=d["estimated_minutes"],
                weight=d["weight"],
            )
            # Сразу создаём экземпляры на неделю вперёд, не дожидаясь часового воркера,
            # иначе ближайшее выполнение не получит ни экземпляра, ни напоминания.
            generate_regular_instances(session, days_ahead=7)

        elif d.get("org_role_name"):
            task = create_task_for_org_role(
                session,
                org_id=info["org_id"],
                title=d["title"],
                description=d.get("description"),
                org_role_name=d["org_role_name"],
                user_ids=d.get("role_user_ids", []),
                estimated_minutes=d["estimated_minutes"],
                weight=d["weight"],
            )
        elif d.get("user_id"):
            task = create_onetime_task_with_instance(
                session,
                org_id=info["org_id"],
                title=d["title"],
                description=d.get("description"),
                user_id=d["user_id"],
                planned_start=d.get("planned_start"),
                planned_end=d["planned_end"],
                estimated_minutes=d["estimated_minutes"],
                weight=d["weight"],
            )
        else:
            task = create_onetime_open_task(
                session,
                org_id=info["org_id"],
                title=d["title"],
                description=d.get("description"),
                planned_end=d["planned_end"],
                estimated_minutes=d["estimated_minutes"],
                weight=d["weight"],
                planned_start=d.get("planned_start"),
            )

        task_id = task.task_id

        # MAX-идентификаторы получателей (в черновике хранятся внутренние User.UserId)
        notify_internal_ids = list(d.get("role_user_ids", [])) if d.get("org_role_name") else (
            [d["user_id"]] if d.get("user_id") else []
        )
        notify_max_ids = [
            r[0] for r in session.query(User.max_id)
            .filter(User.user_id.in_(notify_internal_ids), User.max_id.isnot(None))
            .all()
        ] if notify_internal_ids else []

    clear_state(user_id)
    set_step(user_id, Steps.DONE)
    await event.message.answer(Texts.TASKS_CREATED, attachments=[Buttons.builder_menu.as_markup()])

    # Уведомление исполнителям (по MAX-id, а не по внутреннему UserId)
    for max_id in notify_max_ids:
        try:
            await event.bot.send_message(
                user_id=max_id,
                text=f"Вам назначена задача: {d['title']}",
            )
        except Exception as e:
            logging.warning("Не доставлено %s: %s", max_id, e)

@router.message_callback(F.callback.payload == "task_create")
async def handle_task_create(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        info = check_work(session, user_id)
    if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
        await event.message.answer("Недостаточно полномочий для выполнения операции.")
        return

    clear_state(user_id)
    update_data(user_id, task_draft={})
    set_step(user_id, Steps.TASK_TITLE)
    await event.message.answer(Texts.TASK_TITLE)

def _save(user_id, key, value):
    data = get_data(user_id)
    draft = data.get("task_draft", {})
    draft[key] = value
    update_data(user_id, task_draft=draft)

@router.message_callback(F.callback.payload == "task_assignee_user")
async def handle_task_assignee_user(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        info = check_work(session, user_id)
        rows = get_org_members_full(session, info["org_id"])

    index = {i: u.user_id for i, (_, u, _) in enumerate(rows, start=1)}
    update_data(user_id, task_user_index=index)
    lines = [f"{i}. {(u.user_name or '')} {u.last_name or ''}".strip()
             for i, (_, u, _) in enumerate(rows, start=1)]
    set_step(user_id, Steps.TASK_ASSIGNEE)   # остаёмся на этом шаге, но ждём цифру
    # важно: введём отдельный шаг для ввода номера
    set_step(user_id, "task_assignee_user_number")
    await event.message.answer("Введите номер сотрудника из списка:\n" + "\n".join(lines))

@router.message_callback(F.callback.payload == "task_recurrence_onetime")
async def handle_task_onetime(event: MessageCallback):
    user_id = event.from_user.user_id
    _save(user_id, "is_regular", False)
    set_step(user_id, Steps.TASK_DEADLINE)
    await event.message.answer(Texts.TASK_DEADLINE)


@router.message_callback(F.callback.payload == "task_recurrence_regular")
async def handle_task_regular(event: MessageCallback):
    user_id = event.from_user.user_id
    _save(user_id, "is_regular", True)
    update_data(user_id, task_weekdays=[])
    set_step(user_id, Steps.TASK_WEEKDAYS)
    await event.message.answer(
        Texts.TASK_WEEKDAYS,
        attachments=[Buttons.builder_task_weekdays(set()).as_markup()],
    )

@router.message_callback(F.callback.payload == "task_yes")
async def handle_task_yes(event: MessageCallback):
    user_id = event.from_user.user_id
    step = get_step(user_id)
    if step != Steps.TASK_START_TIME_ASK:
        return
    if get_data(user_id).get("task_draft", {}).get("is_regular"):
        set_step(user_id, Steps.TASK_REGULAR_START_TIME)
        await event.message.answer(Texts.TASK_START_TIME_REGULAR)
        return
    set_step(user_id, Steps.TASK_START_TIME)
    await event.message.answer(Texts.TASK_START_TIME)


@router.message_callback(F.callback.payload == "task_no")
async def handle_task_no(event: MessageCallback):
    user_id = event.from_user.user_id
    step = get_step(user_id)
    if step != Steps.TASK_START_TIME_ASK:
        return
    if get_data(user_id).get("task_draft", {}).get("is_regular"):
        _save(user_id, "start_time", None)
        set_step(user_id, Steps.TASK_PERIOD_ASK)
        await event.message.answer(
            Texts.TASK_PERIOD_ASK,
            attachments=[Buttons.builder_task_period.as_markup()],
        )
        return
    _save(user_id, "planned_start", None)
    set_step(user_id, Steps.TASK_ESTIMATED_MINUTES)
    await event.message.answer(Texts.TASK_ESTIMATED_MINUTES)

@router.message_callback(F.callback.payload.startswith("task_wd_toggle:"))
async def handle_task_wd_toggle(event: MessageCallback):
    user_id = event.from_user.user_id
    bit = int(event.callback.payload.split(":", 1)[1])
    selected = set(get_data(user_id).get("task_weekdays", []))
    if bit in selected:
        selected.remove(bit)
    else:
        selected.add(bit)
    update_data(user_id, task_weekdays=list(selected))

    await event.message.answer(
        Texts.TASK_WEEKDAYS,
        attachments=[Buttons.builder_task_weekdays(selected).as_markup()],
    )


@router.message_callback(F.callback.payload == "task_wd_done")
async def handle_task_wd_done(event: MessageCallback):
    user_id = event.from_user.user_id
    selected = get_data(user_id).get("task_weekdays", [])
    if not selected:
        await event.message.answer(Texts.TASK_WEEKDAYS_MIN)
        return
    mask = sum(selected)
    _save(user_id, "weekday_mask", mask)
    set_step(user_id, Steps.TASK_TIME)
    await event.message.answer(Texts.TASK_TIME)

@router.message_callback(F.callback.payload == "task_period_dates")
async def handle_task_period_dates(event: MessageCallback):
    user_id = event.from_user.user_id
    set_step(user_id, Steps.TASK_PERIOD_START)
    await event.message.answer(Texts.TASK_PERIOD_START)


@router.message_callback(F.callback.payload == "task_period_infinite")
async def handle_task_period_infinite(event: MessageCallback):
    user_id = event.from_user.user_id
    from datetime import date
    _save(user_id, "start_date", date.today())
    _save(user_id, "end_date", None)
    set_step(user_id, Steps.TASK_ESTIMATED_MINUTES)
    await event.message.answer(Texts.TASK_ESTIMATED_MINUTES)

@router.message_callback(F.callback.payload.startswith("task_weight:"))
async def handle_task_weight(event: MessageCallback):
    user_id = event.from_user.user_id
    w = int(event.callback.payload.split(":", 1)[1])
    _save(user_id, "weight", w)

    draft = get_data(user_id).get("task_draft", {})
    text = _format_draft(draft)
    set_step(user_id, Steps.TASK_WEIGHT)   # оставим, но уже ждём кнопку
    set_step(user_id, "task_confirm")
    await event.message.answer(
        Texts.TASK_CONFIRM_TITLE + "\n\n" + text,
        attachments=[Buttons.builder_task_confirm.as_markup()],
    )


def _format_draft(d: dict) -> str:
    lines = [
        f"Название: {d.get('title', '—')}",
        f"Описание: {d.get('description') or '—'}",
    ]
    if d.get("external_role_name"):
        lines.append(f"Внешняя должность: {d['external_role_name']}")
    elif d.get("user_id"):
        lines.append(f"Исполнитель (идентификатор): {d['user_id']}")
    else:
        lines.append("🆓 Свободная (в общий перечень)")

    lines.append(f"Однократная: {'нет' if d.get('is_regular') else 'да'}")
    if d.get("is_regular"):
        lines.append(f"Дни недели (маска): {d.get('weekday_mask')}")
        lines.append(f"Срок исполнения: {d['time'].strftime('%H:%M') if d.get('time') else '—'}")
        start_t = d.get("start_time")
        lines.append(f"Время начала: {start_t.strftime('%H:%M') if start_t else '—'}")

        lines.append(f"{d.get('start_date')} — {d.get('end_date') or '∞'}")
    else:
        lines.append(f"Срок исполнения: {d.get('planned_end')}")
        lines.append(f"Время начала: {d.get('planned_start') or '—'}")

    lines.append(f"Плановая продолжительность (мин): {d.get('estimated_minutes')}")
    lines.append(f"Вес: {d.get('weight')}")
    return "\n".join(lines)

# @router.message_callback(F.callback.payload == "task_confirm_create")
# async def handle_task_confirm_create(event: MessageCallback):
#     user_id = event.from_user.user_id
#     d = get_data(user_id).get("task_draft", {})
#
#     with db.session() as session:
#         info = check_work(session, user_id)
#         if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
#             await event.message.answer("Недостаточно полномочий для выполнения операции.")
#             return
#
#         if d.get("is_regular"):
#             task = create_regular_task(
#                 session,
#                 org_id=info["org_id"],
#                 title=d["title"],
#                 description=d.get("description"),
#                 user_id=d.get("user_id"),
#                 weekday_mask=d["weekday_mask"],
#                 time_=d["time"],
#                 start_date=d["start_date"],
#                 end_date=d.get("end_date"),
#                 deadline_offset=d["deadline_offset"],
#                 estimated_minutes=d["estimated_minutes"],
#                 weight=d["weight"],
#             )
#         elif d.get("external_role_name"):
#             task = create_external_task(
#                 session,
#                 org_id=info["org_id"],
#                 title=d["title"],
#                 description=d.get("description"),
#                 external_role_name=d["external_role_name"],
#                 estimated_minutes=d["estimated_minutes"],
#                 weight=d["weight"],
#             )
#         elif d.get("user_id"):
#             task = create_onetime_task_with_instance(
#                 session,
#                 org_id=info["org_id"],
#                 title=d["title"],
#                 description=d.get("description"),
#                 user_id=d["user_id"],
#                 planned_start=d.get("planned_start"),
#                 planned_end=d["planned_end"],
#                 estimated_minutes=d["estimated_minutes"],
#                 weight=d["weight"],
#             )
#         else:
#             task = create_onetime_open_task(
#                 session,
#                 org_id=info["org_id"],
#                 title=d["title"],
#                 description=d.get("description"),
#                 planned_end=d["planned_end"],
#                 estimated_minutes=d["estimated_minutes"],
#                 weight=d["weight"],
#             )
#
#         task_id = task.task_id
#
#     clear_state(user_id)
#     set_step(user_id, Steps.DONE)
#     await event.message.answer(Texts.TASK_CREATED.format(task_id=task_id))

@router.message_callback(F.callback.payload == "task_cancel")
async def handle_task_cancel(event: MessageCallback):
    user_id = event.from_user.user_id
    clear_state(user_id)
    set_step(user_id, Steps.DONE)
    await event.message.answer(Texts.TASK_CANCELLED, attachments=[Buttons.builder_menu.as_markup()])

@router.message_callback(F.callback.payload == "task_assignee_pool")
async def handle_task_assignee_pool(event: MessageCallback):
    user_id = event.from_user.user_id

    # Запоминаем: назначение «в пул»
    _save(user_id, "is_pool", True)
    _save(user_id, "user_id", None)
    _save(user_id, "org_role_name", None)
    _save(user_id, "role_user_ids", [])

    set_step(user_id, Steps.TASK_RECURRENCE)
    await event.message.answer(
        Texts.TASK_RECURRENCE,
        attachments=[Buttons.builder_task_recurrence.as_markup()],
    )

@router.message_callback(F.callback.payload == "announcement_my_list")
async def handle_announcement_my_list(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0):
            await event.message.answer("Вы не состоите в организации.")
            return
        if info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
            await event.message.answer("Недостаточно полномочий для выполнения операции.")
            return

        author_user_id = info["user_id"]

    # По умолчанию — сегодня
    today = date.today()
    await _show_my_announcements(event, author_user_id, today)


async def _show_my_announcements(event, author_user_id: int, day: date):
    with db.session() as session:
        anns = get_my_announcements_by_day(session, author_user_id, day)

    date_str = day.strftime("%Y-%m-%d")

    if not anns:
        await event.message.answer(
            f"{Texts.ANN_MY_TITLE} за {day.strftime('%d.%m.%Y')}\n\n{Texts.ANN_MY_EMPTY}",
            attachments=[Buttons.builder_ann_my_day(date_str, []).as_markup()],
        )
        return

    lines = [f"{Texts.ANN_MY_TITLE} за {day.strftime('%d.%m.%Y')}\n"]
    for a in anns:
        with db.session() as session:
            stats = get_announcement_stats(session, a.announcement_id)
        t = a.title or "—"
        lines.append(
            f"{t}\n"
            f"   всего: {stats['total']}, "
            f"прочитано: {stats['read']}, "
            f"не прочитано: {stats['unread']}"
        )

    await event.message.answer(
        "\n\n".join(lines),
        attachments=[Buttons.builder_ann_my_day(date_str, anns).as_markup()],
    )


# ---------- Навигация по дням ----------
@router.message_callback(F.callback.payload.startswith("ann_my_shift:"))
async def handle_ann_my_shift(event: MessageCallback):
    user_id = event.from_user.user_id
    parts = event.callback.payload.split(":")
    if len(parts) != 3:
        return
    try:
        day = datetime.strptime(parts[1], "%Y-%m-%d").date()
        delta = int(parts[2])
    except ValueError:
        return

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
            return
        author_user_id = info["user_id"]

    new_day = day + timedelta(days=delta)
    await _show_my_announcements(event, author_user_id, new_day)


# ---------- Другая дата ----------
@router.message_callback(F.callback.payload.startswith("ann_my_pick_date:"))
async def handle_ann_my_pick_date(event: MessageCallback):
    user_id = event.from_user.user_id
    set_step(user_id, Steps.ANN_MY_WAITING_DATE)
    await event.message.answer(Texts.ANN_MY_ASK_DATE)


@router.message_callback(F.callback.payload.startswith("ann_my_day:"))
async def handle_ann_my_day(event: MessageCallback):
    """Возврат к списку по дате (после просмотра одного объявления)."""
    user_id = event.from_user.user_id
    parts = event.callback.payload.split(":")
    if len(parts) != 2:
        return
    try:
        day = datetime.strptime(parts[1], "%Y-%m-%d").date()
    except ValueError:
        return

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
            return
        author_user_id = info["user_id"]

    await _show_my_announcements(event, author_user_id, day)


# ---------- Просмотр одного объявления ----------
@router.message_callback(F.callback.payload.startswith("ann_my_view:"))
async def handle_ann_my_view(event: MessageCallback):
    user_id = event.from_user.user_id
    parts = event.callback.payload.split(":")
    if len(parts) != 2:
        return
    try:
        ann_id = int(parts[1])
    except ValueError:
        return

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
            return

        ann = session.query(Announcement).filter(
            Announcement.announcement_id == ann_id,
            Announcement.author_user_id == info["user_id"],
        ).first()
        if ann is None:
            await event.message.answer(Texts.ANN_MY_NOT_FOUND)
            return

        stats = get_announcement_stats(session, ann_id)
        created = ann.created_at.strftime("%d.%m.%Y %H:%M") if ann.created_at else "—"
        date_str = ann.created_at.strftime("%Y-%m-%d") if ann.created_at else date.today().strftime("%Y-%m-%d")
        text = (
            f"{ann.title or '—'}\n"
            f"{ann.body}\n"
            f"{created}\n\n"
            f"Всего: {stats['total']}\n"
            f"Прочитали: {stats['read']}\n"
            f"Не прочитали: {stats['unread']}"
        )

    await event.message.answer(
        text,
        attachments=[Buttons.builder_ann_my_view(ann_id, date_str).as_markup()],
    )


# ---------- Кто прочитал / не прочитал ----------
@router.message_callback(F.callback.payload.startswith("ann_my_readers:"))
async def handle_ann_my_readers(event: MessageCallback):
    await _show_recipients(event, kind="read")


@router.message_callback(F.callback.payload.startswith("ann_my_unreaders:"))
async def handle_ann_my_unreaders(event: MessageCallback):
    await _show_recipients(event, kind="unread")


async def _show_recipients(event, kind: str):
    user_id = event.from_user.user_id
    parts = event.callback.payload.split(":")
    if len(parts) != 3:
        return
    try:
        ann_id = int(parts[1])
        date_str = parts[2]
    except ValueError:
        return

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
            return

        ann = session.query(Announcement).filter(
            Announcement.announcement_id == ann_id,
            Announcement.author_user_id == info["user_id"],
        ).first()
        if ann is None:
            await event.message.answer(Texts.ANN_MY_NOT_FOUND)
            return

        split = get_announcement_recipients_split(session, ann_id)

    names = split[kind]
    header = "Прочитали:" if kind == "read" else "Не прочитали:"
    if not names:
        body = "— никого"
    else:
        body = "\n".join(f"• {n}" for n in names)

    await event.message.answer(
        f"{header}\n{body}",
        attachments=[Buttons.builder_ann_my_view(ann_id, date_str).as_markup()],
    )

@router.message_callback(F.callback.payload == "get_statistiks")
async def handle_get_statistiks(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        info = check_work(session, user_id)

    if info in (-1, 0):
        await event.message.answer("Вы не состоите в организации.")
        return
    if info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
        await event.message.answer("Недостаточно полномочий для выполнения операции.")
        return

    await event.message.answer(
        Texts.REPORT_TITLE + "\n\n" + Texts.REPORT_CHOOSE,
        attachments=[Buttons.builder_reports.as_markup()],
    )

@router.message_callback(F.callback.payload == "report_employees")
async def handle_report_employees(event: MessageCallback):
    await _send_report(
        event,
        export_employees,
        filename="employees.csv",
        caption="Отчёт по сотрудникам",
    )


@router.message_callback(F.callback.payload == "report_tasks")
async def handle_report_tasks(event: MessageCallback):
    await _send_report(event, export_tasks, filename="tasks.csv", caption="Отчёт по задачам")


@router.message_callback(F.callback.payload == "report_task_completion")
async def handle_report_task_completion(event: MessageCallback):
    await _send_report(event, export_task_completion, filename="task_completion.csv", caption="Отчёт по выполненным задачам")

#
# async def _send_report(event, exporter, filename: str):
#     """Общая обёртка для отчётов без периода."""
#     user_id = event.from_user.user_id
#
#     with db.session() as session:
#         info = check_work(session, user_id)
#         if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
#             await event.message.answer("Недостаточно полномочий для выполнения операции.")
#             return
#
#         try:
#             csv_bytes = exporter(session, info["org_id"])
#         except Exception as e:
#             logging.exception("Report error: %s", e)
#             await event.message.answer(Texts.REPORT_ERROR)
#             return
#
#     await _deliver_csv(event, csv_bytes, filename)

@router.message_callback(F.callback.payload == "report_announcements")
async def handle_report_announcements(event: MessageCallback):
    user_id = event.from_user.user_id
    set_step(user_id, Steps.REPORT_WAITING_DATE_FROM)
    await event.message.answer(Texts.REPORT_ASK_DATE_FROM)

async def _deliver_csv(event, csv_bytes: bytes, filename: str):
    if not csv_bytes:
        await event.message.answer(Texts.REPORT_EMPTY)
        return

    try:
        # точное имя метода зависит от версии maxapi
        await event.bot.send_document(
            user_id=event.from_user.user_id,
            file=csv_bytes,
            filename=filename,
        )
    except AttributeError:
        # fallback, если метода нет
        await _deliver_csv_as_text(event, csv_bytes, filename)

@router.message_callback(F.callback.payload == "my_tasks")
async def handle_my_tasks(event: MessageCallback):
    user_id = event.from_user.user_id

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0):
            await event.message.answer("Вы не состоите в организации.")
            return

        items = get_my_tasks(session, info["user_id"], info["org_id"])

    if not items:
        await event.message.answer(
            Texts.MY_TASKS_EMPTY,
            attachments=[Buttons.builder_my_tasks_list([]).as_markup()],
        )
        return

    # Сортируем: сначала по planned_end (ближайшие первыми), null — в конце
    items.sort(key=lambda x: (x["planned_end"] is None, x["planned_end"] or datetime.max))

    lines = [f"{Texts.MY_TASKS_TITLE}\n"]
    for i, it in enumerate(items, start=1):
        it["number"] = i

        deadline = it["planned_end"].strftime("%d.%m %H:%M") if it["planned_end"] else "—"
        status = "не начата" if it["actual_start"] is None else "в работе"
        lines.append(
            f"{i}. {it['title']}\n"
            f"   Срок: до {deadline}; вес: {it['weight']}; статус: {status}"
        )

    await event.message.answer(
        "\n\n".join(lines),
        attachments=[Buttons.builder_my_tasks_list(items).as_markup()],
    )


# ---------- Просмотр одной задачи ----------
@router.message_callback(F.callback.payload.startswith("my_task_view:"))
async def handle_my_task_view(event: MessageCallback):
    await _show_my_task(event)





# ---------- Подробнее ----------
@router.message_callback(F.callback.payload.startswith("my_task_details:"))
async def handle_my_task_details(event: MessageCallback):
    await _show_my_task(event, detailed=True)


async def _show_my_task(event, detailed: bool = False):
    user_id = event.from_user.user_id
    try:
        instance_id = int(event.callback.payload.split(":", 1)[1])
    except (IndexError, ValueError):
        return

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0):
            await event.message.answer("Вы не состоите в организации.")
            return

        inst = get_task_instance(session, instance_id)
        if inst is None or inst.assignee_user_id != info["user_id"]:
            await event.message.answer(Texts.MY_TASKS_NOT_FOUND)
            return

        # достаём Task для деталей
        task = session.query(Task).filter(Task.task_id == inst.task_id).first()
        if task is None:
            await event.message.answer(Texts.MY_TASKS_NOT_FOUND)
            return

        title = task.title or "—"
        description = task.description or "—"
        planned_start = inst.planned_start.strftime("%d.%m.%Y %H:%M") if inst.planned_start else "—"
        planned_end   = inst.planned_end.strftime("%d.%m.%Y %H:%M") if inst.planned_end else "—"
        actual_start  = inst.actual_start.strftime("%d.%m.%Y %H:%M") if inst.actual_start else "—"
        actual_end    = inst.actual_end.strftime("%d.%m.%Y %H:%M") if inst.actual_end else "—"
        weight = task.weight or 0
        est_min = task.estimated_minutes or 0

        can_start = inst.actual_start is None and inst.actual_end is None
        can_finish = inst.actual_end is None

    text = (
        f"{title}\n\n"
        f"{description}\n\n"
        f"Начало: {planned_start}\n"
        f"Срок исполнения: {planned_end}\n"
        f"Вес: {weight}\n"
        f"Плановая продолжительность: {est_min} мин\n"
        f"Фактическое начало: {actual_start}\n"
        f"Фактическое завершение: {actual_end}"
    )

    await event.message.answer(
        text,
        attachments=[
            Buttons.builder_my_task_actions(
                instance_id,
                can_start=can_start,
                can_finish=can_finish,
            ).as_markup()
        ],
    )


# ---------- Начать выполнение ----------
@router.message_callback(F.callback.payload.startswith("my_task_start:"))
async def handle_my_task_start(event: MessageCallback):
    user_id = event.from_user.user_id
    try:
        instance_id = int(event.callback.payload.split(":", 1)[1])
    except (IndexError, ValueError):
        return

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0):
            return
        ok = start_task(session, instance_id, info["user_id"])

    if ok:
        await event.message.answer(Texts.MY_TASKS_STARTED)
    else:
        await event.message.answer("Не удалось приступить к выполнению: задача уже выполняется либо завершена.")

    await _show_my_task(event)


# ---------- Отметить выполненной ----------
@router.message_callback(F.callback.payload.startswith("my_task_finish:"))
async def handle_my_task_finish(event: MessageCallback):
    user_id = event.from_user.user_id
    try:
        instance_id = int(event.callback.payload.split(":", 1)[1])
    except (IndexError, ValueError):
        return

    with db.session() as session:
        info = check_work(session, user_id)
        if info in (-1, 0):
            return
        ok = finish_task(session, instance_id, info["user_id"])

    if ok:
        await event.message.answer(Texts.MY_TASKS_DONE)
    else:
        await event.message.answer("Не удалось завершить задачу.")

    # Возврат к списку
    await handle_my_tasks(event)


#
# @router.message_callback(F.callback.payload == "staff_list")
# async def handle_staff_list(event: MessageCallback):
#     user_id = event.from_user.user_id
#
#     with db.session() as session:
#         info = check_work(session, user_id)
#         if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
#             await event.message.answer("Недостаточно полномочий для выполнения операции.")
#             return
#
#         rows = get_org_members_full(session, info["org_id"])
#
#     if not rows:
#         await event.message.answer(Texts.STAFF_EMPTY)
#         return
#
#     for member, user, role in rows:
#         name = f"{user.user_name or ''} {user.last_name or ''}".strip() or f"user#{user.user_id}"
#         org_role = member.name_org_role or "—"
#         text = (
#             f"👤 {name}\n"
#             f"🔑 Системная роль: {role.role_name or '—'}\n"
#             f"🏷️ Роль в организации: {org_role}"
#         )
#         await event.message.answer(
#             text,
#             attachments=[Buttons.builder_staff_member(member.member_id).as_markup()],
#         )
#
# @router.message_callback(F.callback.payload.startswith("staff_change_role:"))
# async def handle_staff_change_role(event: MessageCallback):
#     user_id = event.from_user.user_id
#     payload = event.callback.payload
#     try:
#         member_id = int(payload.split(":", 1)[1])
#     except (IndexError, ValueError):
#         return
#
#     with db.session() as session:
#         info = check_work(session, user_id)
#         if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
#             await event.message.answer("Недостаточно полномочий для выполнения операции.")
#             return
#
#         target = get_member_by_id(session, member_id)
#         if target is None or target.organization_id != info["org_id"]:
#             await event.message.answer("Сотрудник не найден в вашей организации.")
#             return
#
#         # админ не может менять роли владельца и других админов
#         if info["role_id"] == ROLE_ADMIN and target.role_id in (ROLE_OWNER, ROLE_ADMIN):
#             await event.message.answer("Администратор не вправе изменять роли владельца и администраторов.")
#             return
#
#     await event.message.answer(
#         Texts.STAFF_ASK_NEW_ROLE,
#         attachments=[Buttons.builder_staff_roles.as_markup()],
#     )
#
# @router.message_callback(F.callback.payload.startswith("staff_set_role:"))
# async def handle_staff_set_role(event: MessageCallback):
#     user_id = event.from_user.user_id
#     payload = event.callback.payload
#     try:
#         new_role_id = int(payload.split(":", 1)[1])
#     except (IndexError, ValueError):
#         return
#
#     with db.session() as session:
#         info = check_work(session, user_id)
#         if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
#             await event.message.answer("Недостаточно полномочий для выполнения операции.")
#             return
#
#         # последний выбранный сотрудник хранится в состоянии — или передавайте member_id в payload
#         data = get_data(user_id)
#         member_id = data.get("staff_target_member_id")
#         if member_id is None:
#             await event.message.answer("Сотрудник не выбран.")
#             return
#
#         target = get_member_by_id(session, member_id)
#         if target is None or target.organization_id != info["org_id"]:
#             await event.message.answer("Сотрудник не найден.")
#             return
#
#         # админ не может назначать владельца/админа
#         if info["role_id"] == ROLE_ADMIN and new_role_id in (ROLE_OWNER, ROLE_ADMIN):
#             await event.message.answer("Администратор не вправе назначать владельца и администраторов.")
#             return
#
#         # нельзя снять владельца, если он один — оставляем владельца всегда
#         if target.role_id == ROLE_OWNER and new_role_id != ROLE_OWNER:
#             await event.message.answer(
#                 "Нельзя понизить владельца. Сначала передайте владение другому сотруднику."
#             )
#             return
#
#         set_member_role(session, member_id, new_role_id)
#
#     clear_state(user_id)
#     set_step(user_id, Steps.DONE)
#     await event.message.answer(Texts.STAFF_ROLE_UPDATED)
#
# @router.message_callback(F.callback.payload.startswith("staff_change_name_role:"))
# async def handle_staff_change_name_role(event: MessageCallback):
#     user_id = event.from_user.user_id
#     payload = event.callback.payload
#     try:
#         member_id = int(payload.split(":", 1)[1])
#     except (IndexError, ValueError):
#         return
#
#     with db.session() as session:
#         info = check_work(session, user_id)
#         if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
#             await event.message.answer("Недостаточно полномочий для выполнения операции.")
#             return
#
#         target = get_member_by_id(session, member_id)
#         if target is None or target.organization_id != info["org_id"]:
#             await event.message.answer("Сотрудник не найден.")
#             return
#
#     update_data(user_id, staff_target_member_id=member_id)
#     set_step(user_id, Steps.STAFF_WAITING_NAME_ORG_ROLE)
#     await event.message.answer(Texts.STAFF_ASK_NAME_ORG_ROLE)
#
# @router.message_callback(F.callback.payload.startswith("staff_fire:"))
# async def handle_staff_fire(event: MessageCallback):
#     user_id = event.from_user.user_id
#     payload = event.callback.payload
#     try:
#         member_id = int(payload.split(":", 1)[1])
#     except (IndexError, ValueError):
#         return
#
#     with db.session() as session:
#         info = check_work(session, user_id)
#         if info in (-1, 0) or info["role_id"] not in (ROLE_OWNER, ROLE_ADMIN):
#             await event.message.answer("Недостаточно полномочий для выполнения операции.")
#             return
#
#         target = get_member_by_id(session, member_id)
#         if target is None or target.organization_id != info["org_id"]:
#             await event.message.answer("Сотрудник не найден.")
#             return
#
#         # защита от увольнения себя
#         if target.member_id == info["member_id"]:
#             await event.message.answer(Texts.STAFF_CANNOT_FIRE_SELF)
#             return
#
#         # владельца уволить нельзя
#         if target.role_id == ROLE_OWNER:
#             await event.message.answer(Texts.STAFF_CANNOT_FIRE_OWNER)
#             return
#
#         # админ не может уволить другого админа
#         if info["role_id"] == ROLE_ADMIN and target.role_id == ROLE_ADMIN:
#             await event.message.answer("Администратор не вправе исключать администраторов.")
#             return
#
#         fire_member(session, member_id)
#
#     await event.message.answer(Texts.STAFF_FIRED)