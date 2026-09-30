import csv
import io
from datetime import datetime, date
from typing import Iterable

from sqlalchemy.orm import Session

from bot.ManagerTextAndButton import Texts
from models import (
    Member, User, Role, Organization,
    Announcement, AnnouncementRecipient,
    Task, TaskInstance,
)

async def _deliver_csv(event, csv_bytes: bytes, filename: str):
    if not csv_bytes:
        await event.message.answer(Texts.REPORT_EMPTY)
        return

    try:
        # если maxapi умеет отправлять файлы
        await event.bot.send_document(
            user_id=event.from_user.user_id,
            file=csv_bytes,
            filename=filename,
        )
    except AttributeError:
        # метода нет — отправляем текст
        await _deliver_csv_as_text(event, csv_bytes, filename)


async def _deliver_csv_as_text(event, csv_bytes: bytes, filename: str):
    """
    Fallback: отправляет CSV как текстовое сообщение.
    Если файл большой — обрезает до лимита MAX.
    """
    text = csv_bytes.decode("utf-8-sig")

    max_len = 3500
    truncated = len(text) > max_len
    if truncated:
        text = text[:max_len]

    body = f"{filename}\n```\n{text}\n```"
    if truncated:
        body += "\nОтображён фрагмент файла."

    await event.message.answer(body)


def _csv_bytes(headers: list[str], rows: Iterable[Iterable]) -> bytes:
    """
    Формирует CSV в памяти и возвращает bytes.
    Используем UTF-8 с BOM, чтобы Excel корректно открывал русские буквы.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
    return buf.getvalue().encode("utf-8-sig")


# ============================================================
# 1. Сотрудники
# ============================================================
def export_employees(db: Session, org_id: int) -> bytes:
    rows = (
        db.query(Member, User, Role)
        .join(User, User.user_id == Member.user_id)
        .join(Role, Role.role_id == Member.role_id)
        .filter(Member.organization_id == org_id)
        .order_by(Member.role_id, User.user_name)
        .all()
    )

    data = []
    for member, user, role in rows:
        data.append([
            user.user_name or "",
            user.last_name or "",
            user.number_phone or "",
            user.max_id or "",
            role.role_name or "",
            member.name_org_role or "",
        ])

    headers = ["Имя", "Фамилия", "Телефон", "MaxId", "Системная роль", "Роль в организации"]
    return _csv_bytes(headers, data)


# ============================================================
# 2. Объявления
# ============================================================
def export_announcements(db: Session, org_id: int, dt_from: date, dt_to: date) -> bytes:
    start = datetime.combine(dt_from, datetime.min.time())
    end = datetime.combine(dt_to, datetime.max.time())

    anns = (
        db.query(Announcement)
        .filter(
            Announcement.organization_id == org_id,
            Announcement.created_at >= start,
            Announcement.created_at <= end,
        )
        .order_by(Announcement.created_at)
        .all()
    )

    data = []
    for a in anns:
        total = (
            db.query(AnnouncementRecipient)
            .filter(AnnouncementRecipient.announcement_id == a.announcement_id)
            .count()
        )
        read = (
            db.query(AnnouncementRecipient)
            .filter(
                AnnouncementRecipient.announcement_id == a.announcement_id,
                AnnouncementRecipient.is_read == True,
            )
            .count()
        )
        data.append([
            a.announcement_id,
            a.created_at.strftime("%d.%m.%Y %H:%M") if a.created_at else "",
            a.title or "",
            (a.body or "").replace("\n", " "),
            total,
            read,
            total - read,
        ])

    headers = ["ID", "Создано", "Заголовок", "Текст", "Адресовано", "Прочитано", "Не прочитано"]
    return _csv_bytes(headers, data)


def export_tasks(db: Session, org_id: int) -> bytes:
    """
    Отчёт по задачам организации с упором на загруженность.

    Что показывает:
      - сколько задач в организации, сколько активных;
      - распределение по исполнителям (по UserId);
      - суммарная плановая нагрузка в часах на каждого исполнителя;
      - средний вес и средняя оценка времени;
      - сколько задач в пуле (без исполнителя);
      - доля активных задач.
    """

    # 1. Все задачи организации
    tasks = (
        db.query(Task)
        .filter(Task.organization_id == org_id)
        .all()
    )

    if not tasks:
        return _csv_bytes(["Показатель", "Значение"], [["Задач нет", ""]])

    # 2. Сводные показатели
    total_tasks   = len(tasks)
    active_tasks  = sum(1 for t in tasks if t.is_active)
    pool_tasks    = sum(1 for t in tasks if not t.user_id)
    total_weight  = sum(t.weight or 0 for t in tasks)
    total_minutes = sum(t.estimated_minutes or 0 for t in tasks)
    avg_weight    = round(total_weight / total_tasks, 2)
    avg_minutes   = round(total_minutes / total_tasks, 1)
    active_share  = round(active_tasks / total_tasks * 100, 1)

    # 3. Загруженность по исполнителям
    #    Считаем: сколько задач на каждого UserId, суммарные минуты, вес
    by_user: dict[int, dict] = {}
    for t in tasks:
        if not t.user_id:
            continue
        u = by_user.setdefault(t.user_id, {
            "tasks": 0, "minutes": 0, "weight": 0,
        })
        u["tasks"]   += 1
        u["minutes"] += t.estimated_minutes or 0
        u["weight"]  += t.weight or 0

    # Имена исполнителей одним запросом
    user_ids = list(by_user.keys())
    users = {}
    if user_ids:
        for u in db.query(User).filter(User.user_id.in_(user_ids)).all():
            users[u.user_id] = f"{u.user_name or ''} {u.last_name or ''}".strip() or f"user#{u.user_id}"

    # 4. Формируем CSV
    headers = ["Раздел", "Показатель", "Значение"]
    data: list[list] = []

    # 4.1. Общие показатели
    data.append(["Общее", "Всего задач", total_tasks])
    data.append(["Общее", "Активных задач", active_tasks])
    data.append(["Общее", "Доля активных, %", active_share])
    data.append(["Общее", "Задач без исполнителя (в общем перечне)", pool_tasks])
    data.append(["Общее", "Суммарный вес", total_weight])
    data.append(["Общее", "Суммарная оценка, мин", total_minutes])
    data.append(["Общее", "Суммарная оценка, ч", round(total_minutes / 60, 1)])
    data.append(["Общее", "Средний вес задачи", avg_weight])
    data.append(["Общее", "Средняя оценка, мин", avg_minutes])

    # 4.2. Загруженность по исполнителям (сортировка по убыванию минут)
    data.append(["", "", ""])
    data.append(["Загруженность", "Исполнитель", "Задач"])
    data.append(["Загруженность", "Исполнитель", "План, мин"])
    data.append(["Загруженность", "Исполнитель", "План, ч"])
    data.append(["Загруженность", "Исполнитель", "Суммарный вес"])

    sorted_users = sorted(
        by_user.items(),
        key=lambda kv: kv[1]["minutes"],
        reverse=True,
    )
    for user_id, agg in sorted_users:
        name = users.get(user_id, f"user#{user_id}")
        data.append(["Загруженность", name, agg["tasks"]])
        data.append(["Загруженность", name, agg["minutes"]])
        data.append(["Загруженность", name, round(agg["minutes"] / 60, 1)])
        data.append(["Загруженность", name, agg["weight"]])

    # 4.3. Топ-5 самых «тяжёлых» задач
    top_tasks = sorted(
        tasks,
        key=lambda t: (t.weight or 0) * (t.estimated_minutes or 0),
        reverse=True,
    )[:5]

    data.append(["", "", ""])
    data.append(["Топ задач", "ID", "Название"])
    data.append(["Топ задач", "ID", "Вес × Минуты"])
    for t in top_tasks:
        data.append(["Топ задач", t.task_id, t.title or ""])
        data.append(["Топ задач", t.task_id, (t.weight or 0) * (t.estimated_minutes or 0)])

    return _csv_bytes(headers, data)

# ============================================================
# 4. Выполнение задач
# ============================================================
def export_task_completion(db: Session, org_id: int) -> bytes:
    rows = (
        db.query(TaskInstance, Task, User)
        .join(Task, Task.task_id == TaskInstance.task_id)
        .outerjoin(User, User.user_id == TaskInstance.assignee_user_id)
        .filter(Task.organization_id == org_id)
        .order_by(TaskInstance.planned_end)
        .all()
    )

    data = []
    for inst, task, user in rows:
        assignee = ""
        if user:
            assignee = f"{user.user_name or ''} {user.last_name or ''}".strip()

        planned_start = inst.planned_start.strftime("%d.%m.%Y %H:%M") if inst.planned_start else ""
        planned_end   = inst.planned_end.strftime("%d.%m.%Y %H:%M") if inst.planned_end else ""
        actual_end    = inst.actual_end.strftime("%d.%m.%Y %H:%M") if inst.actual_end else ""

        data.append([
            inst.instance_id,
            task.title or "",
            assignee,
            planned_start,
            planned_end,
            actual_end,
            inst.actual_minutes or "",
            "да" if inst.actual_end else "нет",
        ])

    headers = ["InstanceId", "Задача", "Исполнитель", "План старт",
               "Плановый срок исполнения", "Факт завершения", "Фактическая продолжительность (мин)", "Выполнена"]
    return _csv_bytes(headers, data)