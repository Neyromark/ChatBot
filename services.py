# # app/services.py
# from typing import Optional
# from sqlalchemy.orm import Session
#
# from models import User
#
# def get_user_by_max_id(db: Session, max_id: int) -> Optional[User]:
#     return db.query(User).filter(User.max_id == max_id).first()
#
#
# def create_user(db: Session, max_id: int, **kwargs) -> User:
#     user = User(max_id=max_id, **kwargs)
#     db.add(user)
#     db.commit()
#     db.refresh(user)
#     return user
#
#
# def get_or_create_user(db: Session, max_id: int, **kwargs) -> User:
#     user = get_user_by_max_id(db, max_id)
#     if user is None:
#         user = create_user(db, max_id=max_id, **kwargs)
#     return user
from datetime import datetime, timedelta, date
# app/services.py
from typing import Optional, List, Union

from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from utils.org_code import decode_org_code, encode_org_id

from models import User, Organization, OrganizationType, Role, Member, AnnouncementRecipient, Announcement, Task, \
    TaskInstance, ScheduleRule


# def check_work(db: Session, max_id: int) -> Union[int, List[str]]:
#     """
#     Возвращает:
#       -1 — пользователя нет в БД
#        0 — пользователь есть, но не в организации
#       [role_name, org_name, city, role_id] — данные о работе
#     """
#     user = db.query(User).filter(User.max_id == max_id).first()
#     if user is None:
#         return -1
#
#     member = db.query(Member).filter(Member.user_id == user.user_id).first()
#     if member is None:
#         return 0
#
#     role = db.query(Role).filter(Role.role_id == member.role_id).first()
#     org = db.query(Organization).filter(
#         Organization.organization_id == member.organization_id
#     ).first()
#
#     role_name = role.role_name if role else "—"
#     org_name = org.org_name if org else "—"
#     city = org.city if org else "—"
#     role_id = member.role_id if member.role_id else 0
#
#     return [role_name, org_name, city, role_id]

def check_work(db: Session, max_id: int) -> Union[int, dict]:
    """
    Возвращает:
      -1 — пользователя нет в БД
       0 — пользователь есть, но не в организации
       dict — данные о работе:
         {
             "role_id":   int,
             "role_name": str,
             "org_id":    int,
             "org_name":  str,
             "city":      str,
             "user_id":   int,
             "member_id": int,
         }
    """
    user = db.query(User).filter(User.max_id == max_id).first()
    if user is None:
        return -1

    member = db.query(Member).filter(Member.user_id == user.user_id).first()
    if member is None:
        return 0

    role = db.query(Role).filter(Role.role_id == member.role_id).first()
    org = db.query(Organization).filter(
        Organization.organization_id == member.organization_id
    ).first()

    return {
        "role_id":   member.role_id or 0,
        "role_name": role.role_name if role else "—",
        "org_id":    member.organization_id or 0,
        "org_name":  org.org_name if org else "—",
        "city":      org.city if org else "—",
        "user_id":   user.user_id,
        "member_id": member.member_id,
    }

# ==========================================
# OrganizationType
# ==========================================
def get_org_type_by_name(db: Session, name: str) -> Optional[OrganizationType]:
    return db.query(OrganizationType).filter(OrganizationType.org_type_name == name).first()


def get_org_type_by_id(db: Session, org_type_id: int) -> Optional[OrganizationType]:
    return db.query(OrganizationType).filter(OrganizationType.org_type_id == org_type_id).first()


def create_org_type(db: Session, name: str) -> OrganizationType:
    org_type = OrganizationType(org_type_name=name)
    db.add(org_type)
    db.commit()
    db.refresh(org_type)
    return org_type


def get_or_create_org_type(db: Session, name: str) -> OrganizationType:
    org_type = get_org_type_by_name(db, name)
    if org_type is None:
        org_type = create_org_type(db, name=name)
    return org_type

def get_all_org_types(db: Session) -> List[OrganizationType]:
    return db.query(OrganizationType).all()

# ==========================================
# User
# ==========================================
def get_user_by_max_id(db: Session, max_id: int) -> Optional[User]:
    return db.query(User).filter(User.max_id == max_id).first()


def create_user(db: Session, max_id: int, **kwargs) -> User:
    user = User(max_id=max_id, **kwargs)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_or_create_user(db: Session, max_id: int, **kwargs) -> User:
    user = get_user_by_max_id(db, max_id)
    if user is None:
        user = create_user(db, max_id=max_id, **kwargs)
    return user


# ==========================================
# Role
# ==========================================
def get_role_by_name(db: Session, name: str) -> Optional[Role]:
    return db.query(Role).filter(Role.role_name == name).first()


def create_role(db: Session, name: str) -> Role:
    role = Role(role_name=name)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def get_or_create_role(db: Session, name: str) -> Role:
    role = get_role_by_name(db, name)
    if role is None:
        role = create_role(db, name=name)
    return role



# ==========================================
# Organization
# ==========================================
def get_organization_by_name(db: Session, name: str) -> Optional[Organization]:
    return db.query(Organization).filter(Organization.org_name == name).first()


def get_organization_by_id(db: Session, org_id: int) -> Optional[Organization]:
    return db.query(Organization).filter(Organization.organization_id == org_id).first()


def create_organization(
    db: Session,
    org_name: str,
    city: Optional[str] = None,
    org_type_id: Optional[int] = None,       # ← было org_type
) -> Organization:
    org = Organization(
        org_name=org_name,
        city=city,
        org_type_id=org_type_id,             # ← было org_type
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def get_or_create_organization(
    db: Session,
    org_name: str,
    city: Optional[str] = None,
    org_type_id: Optional[int] = None,
) -> Organization:
    org = get_organization_by_name(db, org_name)
    if org is None:
        org = create_organization(
            db,
            org_name=org_name,
            city=city,
            org_type_id=org_type_id,
        )
    return org


# ==========================================
# Member (связь user ↔ role ↔ organization)
# ==========================================
def get_member_by_user_id(db: Session, user_id: int) -> Optional[Member]:
    return db.query(Member).filter(Member.user_id == user_id).first()


def get_members_by_user_id(db: Session, user_id: int) -> List[Member]:
    return db.query(Member).filter(Member.user_id == user_id).all()


def create_member(
    db: Session,
    user_id: int,
    role_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    name_org_role: Optional[int] = None,
) -> Member:
    member = Member(
        user_id=user_id,
        role_id=role_id,
        organization_id=organization_id,
        name_org_role=name_org_role,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def get_or_create_member(
    db: Session,
    user_id: int,
    role_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    name_org_role: Optional[int] = None,
) -> Member:
    member = get_member_by_user_id(db, user_id)
    if member is None:
        member = create_member(
            db,
            user_id=user_id,
            role_id=role_id,
            organization_id=organization_id,
            name_org_role=name_org_role,
        )
    return member


def get_organization_by_code(db: Session, code: str) -> Organization | None:
    try:
        org_id = decode_org_code(code)
    except ValueError:
        return None
    return db.query(Organization).filter(Organization.organization_id == org_id).first()


def get_org_code(db: Session, org_id: int) -> str:
    return encode_org_id(org_id)



def get_member_by_user_and_org(db: Session, user_id: int, org_id: int) -> Optional[Member]:
    return (
        db.query(Member)
        .filter(Member.user_id == user_id, Member.organization_id == org_id)
        .first()
    )


def count_org_members(db: Session, org_id: int) -> int:
    return db.query(Member).filter(Member.organization_id == org_id).count()


def delete_organization(db: Session, org_id: int) -> None:
    db.query(Member).filter(Member.organization_id == org_id).delete()
    db.query(Organization).filter(Organization.organization_id == org_id).delete()
    db.commit()

def create_announcement_for_all(session, org_id, author_id, title, body):
    ann = Announcement(
        organization_id=org_id,
        author_user_id=author_id,
        title=title,
        body=body,
    )
    session.add(ann)
    session.flush()   # чтобы получить ann.announcement_id

    # Получаем всех сотрудников организации
    members = session.query(Member).filter(Member.organization_id == org_id).all()

    for m in members:
        session.add(AnnouncementRecipient(
            announcement_id=ann.announcement_id,
            user_id=m.user_id,
            is_read=False,
            read_at=None,
        ))

    session.commit()
    return ann

def create_announcement_for_users(session, org_id, author_id, title, body, user_ids):
    ann = Announcement(
        organization_id=org_id,
        author_user_id=author_id,
        title=title,
        body=body,
    )
    session.add(ann)
    session.flush()

    for uid in user_ids:
        session.add(AnnouncementRecipient(
            announcement_id=ann.announcement_id,
            user_id=uid,
            is_read=False,
        ))

    session.commit()
    return ann

def get_unread_announcements(session, user_id):
    return (
        session.query(Announcement)
        .join(AnnouncementRecipient, AnnouncementRecipient.announcement_id == Announcement.announcement_id)
        .filter(
            AnnouncementRecipient.user_id == user_id,
            AnnouncementRecipient.is_read == False,
        )
        .order_by(Announcement.created_at.desc())
        .all()
    )

def mark_announcement_read(session, announcement_id, user_id):
    rec = (
        session.query(AnnouncementRecipient)
        .filter(
            AnnouncementRecipient.announcement_id == announcement_id,
            AnnouncementRecipient.user_id == user_id,
        )
        .first()
    )
    if rec is None:
        return False

    rec.is_read = True
    rec.read_at = datetime.utcnow()
    session.commit()
    return True

def get_all_org_members(db: Session, org_id: int) -> List[Member]:
    return db.query(Member).filter(Member.organization_id == org_id).all()


def create_announcement(
    db: Session,
    org_id: int,
    author_user_id: int,
    title: str,
    body: str,
    target_user_ids: List[int],
) -> Announcement:
    ann = Announcement(
        organization_id=org_id,
        author_user_id=author_user_id,
        title=title,
        body=body,
    )
    db.add(ann)
    db.flush()   # получаем ann.announcement_id

    for uid in target_user_ids:
        db.add(AnnouncementRecipient(
            announcement_id=ann.announcement_id,
            user_id=uid,
            is_read=False,
        ))

    db.commit()
    db.refresh(ann)
    return ann


def get_unread_for_user(db: Session, user_id: int) -> List[Announcement]:
    return (
        db.query(Announcement)
        .join(AnnouncementRecipient,
              AnnouncementRecipient.announcement_id == Announcement.announcement_id)
        .filter(
            AnnouncementRecipient.user_id == user_id,
            AnnouncementRecipient.is_read == False,
        )
        .order_by(Announcement.created_at.desc())
        .all()
    )


def mark_announcement_read(db: Session, announcement_id: int, user_id: int) -> bool:
    rec = (
        db.query(AnnouncementRecipient)
        .filter(
            AnnouncementRecipient.announcement_id == announcement_id,
            AnnouncementRecipient.user_id == user_id,
        )
        .first()
    )
    if rec is None:
        return False
    rec.is_read = True
    rec.read_at = datetime.utcnow()
    db.commit()
    return True

def get_org_info(db: Session, org_id: int) -> dict:
    org = db.query(Organization).filter(Organization.organization_id == org_id).first()
    if org is None:
        return {}

    org_type = db.query(OrganizationType).filter(
        OrganizationType.org_type_id == org.org_type_id
    ).first()

    members_count = db.query(Member).filter(Member.organization_id == org_id).count()

    return {
        "org_id":        org.organization_id,
        "org_name":      org.org_name or "—",
        "city":          org.city or "—",
        "org_type_id":   org.org_type_id or 0,
        "org_type_name": org_type.org_type_name if org_type else "—",
        "members_count": members_count,
    }


def get_org_members_stats(db: Session, org_id: int) -> List[dict]:
    """Количество сотрудников по ролям."""
    rows = (
        db.query(Role.role_id, Role.role_name, func.count(Member.member_id))
        .join(Member, Member.role_id == Role.role_id)
        .filter(Member.organization_id == org_id)
        .group_by(Role.role_id, Role.role_name)
        .all()
    )
    return [
        {"role_id": r[0], "role_name": r[1], "count": r[2]}
        for r in rows
    ]


def get_org_announcements_stats(db: Session, org_id: int) -> dict:
    """Статистика по объявлениям организации."""
    total = (
        db.query(func.count(Announcement.announcement_id))
        .filter(Announcement.organization_id == org_id)
        .scalar() or 0
    )

    delivered = (
        db.query(func.count(AnnouncementRecipient.announcement_id))
        .join(Announcement, Announcement.announcement_id == AnnouncementRecipient.announcement_id)
        .filter(Announcement.organization_id == org_id)
        .scalar() or 0
    )

    read = (
        db.query(func.count(AnnouncementRecipient.announcement_id))
        .join(Announcement, Announcement.announcement_id == AnnouncementRecipient.announcement_id)
        .filter(
            Announcement.organization_id == org_id,
            AnnouncementRecipient.is_read == True,
        )
        .scalar() or 0
    )

    return {
        "total":     total,
        "delivered": delivered,
        "read":      read,
        "unread":    delivered - read,
    }

def update_org_name(db: Session, org_id: int, name: str) -> None:
    org = db.query(Organization).filter(Organization.organization_id == org_id).first()
    if org:
        org.org_name = name
        db.commit()


def update_org_city(db: Session, org_id: int, city: str) -> None:
    org = db.query(Organization).filter(Organization.organization_id == org_id).first()
    if org:
        org.city = city
        db.commit()


def update_org_type(db: Session, org_id: int, org_type_id: int) -> None:
    org = db.query(Organization).filter(Organization.organization_id == org_id).first()
    if org:
        org.org_type_id = org_type_id
        db.commit()


def get_all_org_types(db: Session):
    return db.query(OrganizationType).order_by(OrganizationType.org_type_id).all()

def get_unread_announcements(db: Session, user_id: int) -> List[Announcement]:
    """Непрочитанные объявления пользователя."""
    return (
        db.query(Announcement)
        .join(AnnouncementRecipient,
              AnnouncementRecipient.announcement_id == Announcement.announcement_id)
        .filter(
            AnnouncementRecipient.user_id == user_id,
            AnnouncementRecipient.is_read == False,
        )
        .order_by(Announcement.created_at.desc())
        .all()
    )


def get_today_announcements(db: Session, user_id: int) -> List[Announcement]:
    """Объявления, созданные сегодня, доступные пользователю."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)

    return (
        db.query(Announcement)
        .join(AnnouncementRecipient,
              AnnouncementRecipient.announcement_id == Announcement.announcement_id)
        .filter(
            AnnouncementRecipient.user_id == user_id,
            Announcement.created_at >= today_start,
            Announcement.created_at < tomorrow_start,
        )
        .order_by(Announcement.created_at.desc())
        .all()
    )


def search_announcements_by_title(db: Session, user_id: int, query: str) -> List[Announcement]:
    """Поиск по части названия через LIKE (регистронезависимо)."""
    pattern = f"%{query}%"
    return (
        db.query(Announcement)
        .join(AnnouncementRecipient,
              AnnouncementRecipient.announcement_id == Announcement.announcement_id)
        .filter(
            AnnouncementRecipient.user_id == user_id,
            Announcement.title.ilike(pattern),
        )
        .order_by(Announcement.created_at.desc())
        .all()
    )


def search_announcements_by_date(db: Session, user_id: int, date_: datetime) -> List[Announcement]:
    """Поиск объявлений за конкретный день."""
    day_start = date_.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    return (
        db.query(Announcement)
        .join(AnnouncementRecipient,
              AnnouncementRecipient.announcement_id == Announcement.announcement_id)
        .filter(
            AnnouncementRecipient.user_id == user_id,
            Announcement.created_at >= day_start,
            Announcement.created_at < day_end,
        )
        .order_by(Announcement.created_at.desc())
        .all()
    )

def get_org_members_full(db: Session, org_id: int) -> List[tuple]:
    """Список (Member, User, Role) для организации."""
    return (
        db.query(Member, User, Role)
        .join(User, User.user_id == Member.user_id)
        .join(Role, Role.role_id == Member.role_id)
        .filter(Member.organization_id == org_id)
        .order_by(Member.role_id, User.user_name)
        .all()
    )


def get_member_by_id(db: Session, member_id: int) -> Optional[Member]:
    return db.query(Member).filter(Member.member_id == member_id).first()


def set_member_role(db: Session, member_id: int, role_id: int) -> None:
    m = db.query(Member).filter(Member.member_id == member_id).first()
    if m:
        m.role_id = role_id
        db.commit()


def set_member_name_org_role(db: Session, member_id: int, name: str) -> None:
    m = db.query(Member).filter(Member.member_id == member_id).first()
    if m:
        # если NameOrgRole — INT, храните ID роли; иначе строка.
        # Предполагаем, что вы хотите хранить текст — замените тип колонки на NVARCHAR.
        m.name_org_role = name
        db.commit()


def fire_member(db: Session, member_id: int) -> None:
    m = db.query(Member).filter(Member.member_id == member_id).first()
    if m:
        db.delete(m)
        db.commit()

def get_users_by_org_role_name(db: Session, org_id: int, role_name: str) -> List[User]:
    """
    Возвращает пользователей организации, у которых Member.NameOrgRole
    равен заданному названию роли (регистронезависимо).
    """
    rows = (
        db.query(User)
        .join(Member, Member.user_id == User.user_id)
        .filter(
            Member.organization_id == org_id,
            Member.name_org_role.ilike(role_name),
        )
        .all()
    )
    return rows


def create_task_for_org_role(
    db: Session,
    org_id: int,
    title: str,
    description,
    org_role_name: str,
    user_ids: List[int],
    estimated_minutes: int,
    weight: int,
) -> Task:
    """
    Создаёт Task с external_role_name=org_role_name
    и по Task_Instance на каждого user_id.
    """
    task = Task(
        organization_id=org_id,
        title=title,
        description=description,
        external_role_name=org_role_name,     # используем это поле как "роль в организации"
        estimated_minutes=estimated_minutes,
        weight=weight,
        is_active=True,
    )
    db.add(task)
    db.flush()

    for uid in user_ids:
        inst = TaskInstance(
            task_id=task.task_id,
            assignee_user_id=uid,
            status_id=1,
            planned_start=None,
            planned_end=None,
            is_taken=True,
        )
        db.add(inst)

    db.commit()
    db.refresh(task)
    return task

def create_onetime_task_with_instance(
    db: Session,
    org_id: int,
    title: str,
    description,
    user_id: int,
    planned_start,
    planned_end,
    estimated_minutes: int,
    weight: int,
) -> Task:
    """
    Разовая задача на конкретного сотрудника.
    Создаёт:
      - Schedule_Rule-заглушку с одним днём = дата дедлайна, Time = время дедлайна,
        WeekdayMask = 0 (в маске «ни одного дня»),
        StartDate = EndDate = дата дедлайна.
      - Task с привязкой к этому правилу.
      - Task_Instance с PlannedStart / PlannedEnd, AssigneeUserId = user_id, IsTaken = True.
    """
    # 1. Заглушка Schedule_Rule
    if planned_end is not None:
        deadline_date = planned_end.date()
        deadline_time = planned_end.time()
    else:
        # на случай, если дедлайн всё-таки не задан
        deadline_date = datetime.utcnow().date()
        deadline_time = datetime.utcnow().time()

    rule = ScheduleRule(
        weekday_mask=0,                 # ни одного дня (разовая)
        time=deadline_time,
        start_date=deadline_date,
        end_date=deadline_date,
        interval=None,
    )
    db.add(rule)
    db.flush()   # получаем rule.rule_id

    # 2. Task
    task = Task(
        organization_id=org_id,
        title=title,
        description=description,
        user_id=user_id,
        schedule_rule_id=rule.rule_id,
        deadline_offset=None,
        estimated_minutes=estimated_minutes,
        weight=weight,
        is_active=True,
    )
    db.add(task)
    db.flush()

    # 3. Task_Instance
    inst = TaskInstance(
        task_id=task.task_id,
        assignee_user_id=user_id,
        status_id=1,
        planned_start=planned_start,
        planned_end=planned_end,
        is_taken=True,
    )
    db.add(inst)
    db.commit()
    db.refresh(task)
    return task

def create_onetime_open_task(
    db: Session,
    org_id: int,
    title: str,
    description,
    planned_end,
    estimated_minutes: int,
    weight: int,
    planned_start=None,
) -> Task:
    task = Task(
        organization_id=org_id,
        title=title,
        description=description,
        estimated_minutes=estimated_minutes,
        weight=weight,
        is_active=True,
    )
    db.add(task)
    db.flush()

    inst = TaskInstance(
        task_id=task.task_id,
        assignee_user_id=None,
        status_id=1,
        planned_start=planned_start,
        planned_end=planned_end,
        is_taken=False,
    )
    db.add(inst)
    db.commit()
    db.refresh(task)
    return task


def create_regular_task(
    db: Session,
    org_id: int,
    title: str,
    description,
    user_id,
    weekday_mask: int,
    time_,
    start_date,
    end_date,
    estimated_minutes: int,
    weight: int,
    start_time=None,
) -> Task:
    """
    Регулярная задача, как и разовая, ориентирована на дедлайн:
      time_      — дедлайн (время суток), обязателен;
      start_time — время начала (время суток, раньше дедлайна), необязательно.
    Хранение (схему БД не меняем):
      если начало задано — Schedule_Rule.Time = начало, Task.DeadlineOffset = МИНУТЫ от начала до дедлайна;
      если нет — Schedule_Rule.Time = дедлайн, Task.DeadlineOffset = NULL
      (так же, как у разовой задачи, где в правиле лежит время дедлайна).
    Экземпляры по этому правилу создаёт generate_regular_instances.
    """
    if start_time is not None:
        rule_time = start_time
        deadline_offset = (time_.hour * 60 + time_.minute) - (start_time.hour * 60 + start_time.minute)
    else:
        rule_time = time_
        deadline_offset = None

    rule = ScheduleRule(
        weekday_mask=weekday_mask,
        time=rule_time,
        start_date=start_date,
        end_date=end_date,
        interval=None,
    )
    db.add(rule)
    db.flush()

    task = Task(
        organization_id=org_id,
        title=title,
        description=description,
        user_id=user_id,
        schedule_rule_id=rule.rule_id,
        deadline_offset=deadline_offset,
        estimated_minutes=estimated_minutes,
        weight=weight,
        is_active=True,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def create_external_task(
    db: Session,
    org_id: int,
    title: str,
    description,
    external_role_name: str,
    estimated_minutes: int,
    weight: int,
) -> Task:
    task = Task(
        organization_id=org_id,
        title=title,
        description=description,
        external_role_name=external_role_name,
        estimated_minutes=estimated_minutes,
        weight=weight,
        is_active=True,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

def create_task(
    db: Session,
    org_id: int,
    title: str,
    description: Optional[str],
    user_id: Optional[int] = None,
    # role_id: Optional[int] = None,          ← УДАЛЕНО
    external_role_name: Optional[str] = None,
    weight: int = 1,
    estimated_minutes: int = 60,
) -> Task:
    task = Task(
        organization_id=org_id,
        title=title,
        description=description,
        user_id=user_id,
        # role_id=role_id,                    ← УДАЛЕНО
        external_role_name=external_role_name,
        weight=weight,
        estimated_minutes=estimated_minutes,
        is_active=True,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


# --- Активные задачи: кто что делает ---
def get_active_instances(db: Session, org_id: int) -> List[dict]:
    """
    Задачи, которые сейчас выполняются: Task_Instance с AssigneeUserId
    и статусом, который мы считаем «в работе». Здесь — просто «есть исполнитель».
    """
    rows = (
        db.query(TaskInstance, Task, User)
        .join(Task, Task.task_id == TaskInstance.task_id)
        .join(User, User.user_id == TaskInstance.assignee_user_id)
        .filter(
            Task.organization_id == org_id,
            TaskInstance.assignee_user_id.isnot(None),
            TaskInstance.actual_end.is_(None),   # ещё не завершена
        )
        .order_by(
            # Сначала задачи с заполненным planned_end (0), затем с NULL (1)
            case(
                (TaskInstance.planned_end.is_(None), 1),
                else_=0,
            ).asc(),
            TaskInstance.planned_end.asc(),
        )
        .all()
    )
    result = []
    for inst, task, user in rows:
        fio = f"{user.user_name or ''} {user.last_name or ''}".strip() or f"user#{user.user_id}"
        result.append({
            "instance_id": inst.instance_id,
            "task_id": task.task_id,
            "title": task.title,
            "assignee": fio,
            "planned_end": inst.planned_end,
            "weight": task.weight,
        })
    return result

from sqlalchemy import case

# --- Свободные задачи (пул) с дедлайном ---
def get_pool_instances(
    db: Session,
    org_id: int,
    hours_ahead: int = 48,
    member_id: Optional[int] = None,
) -> List[dict]:
    """
    Задачи в пуле: AssigneeUserId IS NULL, IsTaken = 0,
    и (плановое время подошло ИЛИ дедлайн в ближайшие N часов).

    member_id: если передан (обычный сотрудник), показываем только задачи, назначенные
    ему: без ограничения по роли (Task.ExternalRoleName IS NULL) либо на его роль
    в организации (Member.NameOrgRole). Владелец и админ передают None и видят весь пул.
    """
    horizon = datetime.utcnow() + timedelta(hours=hours_ahead)

    query = (
        db.query(TaskInstance, Task)
        .join(Task, Task.task_id == TaskInstance.task_id)
        .filter(
            Task.organization_id == org_id,
            TaskInstance.assignee_user_id.is_(None),
            TaskInstance.is_taken == False,
            or_(
                TaskInstance.planned_start <= horizon,
                TaskInstance.planned_end <= horizon,
            ),
        )
    )

    if member_id is not None:
        member = db.query(Member).filter(Member.member_id == member_id).first()
        my_role = member.name_org_role if member else None
        if my_role:
            query = query.filter(
                or_(Task.external_role_name.is_(None), Task.external_role_name == my_role)
            )
        else:
            query = query.filter(Task.external_role_name.is_(None))

    rows = (
        query
        .order_by(
            # Сначала задачи с заполненным planned_end (0), затем с NULL (1)
            case(
                (TaskInstance.planned_end.is_(None), 1),
                else_=0,
            ).asc(),
            TaskInstance.planned_end.asc(),
        )
        .all()
    )
    result = []
    for i, (inst, task) in enumerate(rows, start=1):
        result.append({
            "number": i,
            "instance_id": inst.instance_id,
            "task_id": task.task_id,
            "title": task.title,
            "planned_end": inst.planned_end,
            "weight": task.weight,
        })
    return result


# --- Взять задачу из пула ---
def take_task_from_pool(db: Session, instance_id: int, user_id: int, org_id: Optional[int] = None) -> bool:
    """
    Атомарно берёт задачу из пула одним UPDATE с условием в WHERE.
    Если два сотрудника нажмут одновременно, БД выполнит UPDATE для одного из них,
    у второго rowcount будет 0, и он получит False.
    При взятии заполняем ActualStart.
    """
    q = db.query(TaskInstance).filter(
        TaskInstance.instance_id == instance_id,
        TaskInstance.is_taken == False,
        TaskInstance.assignee_user_id.is_(None),
    )
    if org_id is not None:
        q = q.filter(
            TaskInstance.task_id.in_(
                db.query(Task.task_id).filter(Task.organization_id == org_id)
            )
        )
    updated = (
        q
        .update(
            {
                TaskInstance.assignee_user_id: user_id,
                TaskInstance.is_taken: True,
                TaskInstance.actual_start: datetime.utcnow(),
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return updated == 1


# --- Редактирование ---
def update_task_field(db: Session, task_id: int, field: str, value) -> bool:
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if task is None:
        return False
    setattr(task, field, value)
    db.commit()
    return True

def get_my_announcements_by_day(
    db: Session, author_user_id: int, day: date
) -> List[Announcement]:
    """Объявления автора за конкретный день (по CreatedAt)."""
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)

    return (
        db.query(Announcement)
        .filter(
            Announcement.author_user_id == author_user_id,
            Announcement.created_at >= start,
            Announcement.created_at < end,
        )
        .order_by(Announcement.created_at.desc())
        .all()
    )


def get_announcement_stats(db: Session, announcement_id: int) -> dict:
    """Всего адресовано, прочитано, не прочитано."""
    total = (
        db.query(AnnouncementRecipient)
        .filter(AnnouncementRecipient.announcement_id == announcement_id)
        .count()
    )
    read = (
        db.query(AnnouncementRecipient)
        .filter(
            AnnouncementRecipient.announcement_id == announcement_id,
            AnnouncementRecipient.is_read == True,
        )
        .count()
    )
    return {"total": total, "read": read, "unread": total - read}


def get_announcement_recipients_split(
    db: Session, announcement_id: int
) -> dict:
    """
    Возвращает {'read': [ФИО, ...], 'unread': [ФИО, ...]}.
    ФИО собираем из User + Member.
    """
    rows = (
        db.query(AnnouncementRecipient.is_read, User.user_name, User.last_name)
        .join(User, User.user_id == AnnouncementRecipient.user_id)
        .filter(AnnouncementRecipient.announcement_id == announcement_id)
        .all()
    )

    read, unread = [], []
    for is_read, name, last_name in rows:
        fio = f"{name or ''} {last_name or ''}".strip() or "—"
        (read if is_read else unread).append(fio)

    return {"read": read, "unread": unread}

def _today_range() -> tuple[datetime, datetime]:
    start = datetime.combine(date.today(), datetime.min.time())
    end = start + timedelta(days=1)
    return start, end


def get_my_tasks(db: Session, user_id: int, org_id: int) -> List[dict]:
    """
    Возвращает список активных задач пользователя:
      1) Разовые Task_Instance с assignee_user_id = user_id и фактически не завершённые
         (actual_end IS NULL), независимо от planned_end.
      2) Экземпляры регулярных задач тоже лежат в Task_Instance: их на неделю вперёд
         создаёт generate_regular_instances (вызывается фоновым воркером).
    """

    result: list[dict] = []

    # 1. Активные Task_Instance пользователя
    instances = (
        db.query(TaskInstance, Task)
        .join(Task, Task.task_id == TaskInstance.task_id)
        .filter(
            Task.organization_id == org_id,
            TaskInstance.assignee_user_id == user_id,
            TaskInstance.actual_end.is_(None),
        )
        .all()
    )

    for inst, task in instances:
        result.append({
            "instance_id": inst.instance_id,
            "task_id": task.task_id,
            "title": task.title or "—",
            "description": task.description or "",
            "planned_start": inst.planned_start,
            "planned_end": inst.planned_end,
            "actual_start": inst.actual_start,
            "status_id": inst.status_id,
            "weight": task.weight,
            "estimated_minutes": task.estimated_minutes,
            "is_taken": inst.is_taken,
        })

    return result


def generate_regular_instances(db: Session, days_ahead: int = 7) -> int:
    """
    Дополняет Task_Instance для регулярных задач (Schedule_Rule.WeekdayMask != 0)
    на `days_ahead` дней вперёд (включая сегодня). Возвращает число созданных строк.

    Регулярная задача, как и разовая, ориентирована на дедлайн. Для каждой подходящей даты:
      если Task.DeadlineOffset задан (у задачи есть время начала):
          PlannedStart = дата + Schedule_Rule.Time,
          PlannedEnd   = PlannedStart + DeadlineOffset МИНУТ;
      иначе (только дедлайн):
          PlannedStart = NULL, PlannedEnd = дата + Schedule_Rule.Time.
      AssigneeUserId = Task.UserId; если он не задан, экземпляр уходит в пул (IsTaken = 0).
    Регулярные задачи обязательные: у назначенного сотрудника IsTaken = 1, принятия нет.

    Идемпотентно: экземпляр с тем же (TaskId, PlannedEnd) повторно не создаётся,
    поэтому функцию безопасно вызывать сколько угодно раз. Задачи с прошедшим дедлайном пропускаются.
    """
    now = datetime.now()
    today = now.date()
    created = 0

    rows = (
        db.query(Task, ScheduleRule)
        .join(ScheduleRule, ScheduleRule.rule_id == Task.schedule_rule_id)
        .filter(
            Task.is_active == True,
            ScheduleRule.weekday_mask != 0,
            ScheduleRule.start_date <= today + timedelta(days=days_ahead),
            or_(ScheduleRule.end_date.is_(None), ScheduleRule.end_date >= today),
        )
        .all()
    )

    for task, rule in rows:
        for offset in range(days_ahead + 1):
            day = today + timedelta(days=offset)
            if day < rule.start_date:
                continue
            if rule.end_date is not None and day > rule.end_date:
                continue
            if not (rule.weekday_mask & (1 << day.weekday())):   # Пн = 1, Вт = 2, ... Вс = 64
                continue

            if task.deadline_offset is not None:
                planned_start = datetime.combine(day, rule.time)
                planned_end = planned_start + timedelta(minutes=task.deadline_offset)
            else:
                planned_start = None
                planned_end = datetime.combine(day, rule.time)

            if planned_end < now:
                continue

            exists = (
                db.query(TaskInstance.instance_id)
                .filter(
                    TaskInstance.task_id == task.task_id,
                    TaskInstance.planned_end == planned_end,
                )
                .first()
            )
            if exists:
                continue


            has_assignee = task.user_id is not None
            db.add(TaskInstance(
                task_id=task.task_id,
                assignee_user_id=task.user_id,
                status_id=1,
                planned_start=planned_start,
                planned_end=planned_end,
                is_taken=has_assignee,
            ))
            created += 1

    db.commit()
    return created



def get_task_instance(db: Session, instance_id: int) -> TaskInstance | None:
    return db.query(TaskInstance).filter(TaskInstance.instance_id == instance_id).first()


def start_task(db: Session, instance_id: int, user_id: int) -> bool:
    inst = get_task_instance(db, instance_id)
    if inst is None or inst.assignee_user_id != user_id:
        return False
    if inst.actual_end is not None:
        return False
    inst.actual_start = datetime.utcnow()
    # status_id можно поменять на "в работе", если у вас есть такая
    db.commit()
    return True


def finish_task(db: Session, instance_id: int, user_id: int) -> bool:
    inst = get_task_instance(db, instance_id)
    if inst is None or inst.assignee_user_id != user_id:
        return False
    now = datetime.utcnow()
    if inst.actual_start is None:
        inst.actual_start = now
    inst.actual_end = now
    # посчитаем фактические минуты, если есть actual_start
    if inst.actual_start:
        delta = now - inst.actual_start
        inst.actual_minutes = max(int(delta.total_seconds() // 60), 0)
    # status_id можно поменять на "выполнено"
    db.commit()
    return True