from sqlalchemy import (Column, Integer, String, Unicode, UnicodeText, ForeignKey, BigInteger, Text, DateTime,
                        PrimaryKeyConstraint, Boolean, func, Date, Time, CheckConstraint)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

ROLE_OWNER = 1
ROLE_ADMIN = 2
ROLE_EMPLOYEE = 3


class User(Base):
    __tablename__ = 'User'
    user_id = Column('UserId', Integer, primary_key=True, autoincrement=True)
    user_name = Column('UserName', Unicode(50), nullable=True)
    last_name = Column('LastName', Unicode(150), nullable=True)   # ← было 12, мало для фамилии
    number_phone = Column('NumberPhone', Unicode(20), nullable=True)  # ← было Integer
    max_id = Column('MaxId', BigInteger, nullable=True)          # ← было Integer

    # Связь с Member (один пользователь → много записей в Member)
    members = relationship("Member", back_populates="user")

    def __repr__(self):
        return (f"<User(user_id={self.user_id}, "
                f"user_name='{self.user_name}', "
                f"last_name='{self.last_name}')>")


class Role(Base):
    __tablename__ = 'Role'
    role_id = Column('RoleId', Integer, primary_key=True, autoincrement=True)
    role_name = Column('RoleName', Unicode(50), nullable=True)

    members = relationship("Member", back_populates="role")

    def __repr__(self):
        return f"<Role(role_id={self.role_id}, role_name='{self.role_name}')>"


class OrganizationType(Base):
    __tablename__ = 'OrganizationType'
    org_type_id = Column('OrgTypeId', Integer, primary_key=True, autoincrement=True)
    org_type_name = Column('OrgTypeName', Unicode(50), nullable=True)

    organizations = relationship("Organization", back_populates="org_type")

    def __repr__(self):
        return (f"<OrganizationType(org_type_id={self.org_type_id}, "
                f"org_type_name='{self.org_type_name}')>")


class Organization(Base):
    __tablename__ = 'Organization'
    organization_id = Column('OrganizationId', Integer, primary_key=True, autoincrement=True)
    org_name = Column('OrgName', Unicode(50), nullable=True)
    city = Column('City', Unicode(50), nullable=True)
    org_type_id = Column('OrgTypeId', Integer, ForeignKey('OrganizationType.OrgTypeId'), nullable=True)

    org_type = relationship("OrganizationType", back_populates="organizations")
    members = relationship("Member", back_populates="organization")

    def __repr__(self):
        return (f"<Organization(organization_id={self.organization_id}, "
                f"org_name='{self.org_name}', city='{self.city}', "
                f"org_type_id={self.org_type_id})>")


class Member(Base):
    __tablename__ = 'Member'
    member_id = Column('MemberId', Integer, primary_key=True, autoincrement=True)
    organization_id = Column('OrganizationId', Integer, ForeignKey('Organization.OrganizationId'), nullable=True)
    role_id = Column('RoleId', Integer, ForeignKey('Role.RoleId'), nullable=True)
    user_id = Column('UserId', Integer, ForeignKey('User.UserId'), nullable=True)
    name_org_role = Column('NameOrgRole', Unicode(50), nullable=True)

    organization = relationship("Organization", back_populates="members")
    role = relationship("Role", back_populates="members")
    user = relationship("User", back_populates="members")

    def __repr__(self):
        return (f"<Member(member_id={self.member_id}, "
                f"user_id={self.user_id}, role_id={self.role_id}, "
                f"organization_id={self.organization_id})>")

class Announcement(Base):
    __tablename__ = "Announcement"

    announcement_id = Column("AnnouncementId", Integer, primary_key=True, autoincrement=True)
    organization_id = Column("OrganizationId", Integer, ForeignKey("Organization.OrganizationId"), nullable=False)
    author_user_id  = Column("AuthorUserId",   Integer, ForeignKey("User.UserId"), nullable=False)
    title           = Column("Title", Unicode(150), nullable=True)
    body            = Column("Body", UnicodeText, nullable=False)
    created_at      = Column("CreatedAt", DateTime, server_default=func.now())

    recipients = relationship(
        "AnnouncementRecipient",
        back_populates="announcement",
        cascade="all, delete-orphan",
    )


class AnnouncementRecipient(Base):
    __tablename__ = "AnnouncementRecipient"
    __table_args__ = (
        PrimaryKeyConstraint("AnnouncementId", "UserId"),
    )

    announcement_id = Column("AnnouncementId", Integer, ForeignKey("Announcement.AnnouncementId", ondelete="CASCADE"), nullable=False)
    user_id         = Column("UserId", Integer, ForeignKey("User.UserId"), nullable=False)
    is_read         = Column("IsRead", Boolean, nullable=False, default=False)
    read_at         = Column("ReadAt", DateTime, nullable=True)

    announcement = relationship("Announcement", back_populates="recipients")

# ============================================================
# Schedule_Rule — правило повторения
# ============================================================
class ScheduleRule(Base):
    __tablename__ = "Schedule_Rule"

    rule_id       = Column("RuleId", Integer, primary_key=True, autoincrement=True)
    weekday_mask  = Column("WeekdayMask", Integer, nullable=False)
    time          = Column("Time", Time, nullable=False)
    start_date    = Column("StartDate", Date, nullable=False)
    end_date      = Column("EndDate", Date, nullable=True)
    interval      = Column("Interval", Integer, nullable=True)
    created_at    = Column("CreatedAt", DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "WeekdayMask BETWEEN 0 AND 127",     # ← было 1..127
            name="CK_Schedule_Rule_WeekdayMask",
        ),
        CheckConstraint("[Interval] IS NULL OR [Interval] > 0", name="CK_Schedule_Rule_Interval"),
        CheckConstraint("EndDate IS NULL OR EndDate >= StartDate", name="CK_Schedule_Rule_Dates"),
    )

# ============================================================
# Task — шаблон задачи
# ============================================================
class Task(Base):
    __tablename__ = "Task"

    task_id         = Column("TaskId", Integer, primary_key=True, autoincrement=True)
    organization_id = Column("OrganizationId", Integer, nullable=False)
    title           = Column("Title", Unicode(200), nullable=False)
    description     = Column("Description", UnicodeText, nullable=True)

    user_id            = Column("UserId", Integer, nullable=True)
    # role_id          = Column("RoleId", Integer, nullable=True)   ← УДАЛЕНО
    external_role_name = Column("ExternalRoleName", Unicode(100), nullable=True)

    schedule_rule_id   = Column("ScheduleRuleId", Integer, ForeignKey("Schedule_Rule.RuleId"), nullable=True)
    estimated_minutes  = Column("EstimatedMinutes", Integer, nullable=False, default=60)
    weight             = Column("Weight", Integer, nullable=False, default=1)
    deadline_offset    = Column("DeadlineOffset", Integer, nullable=True)

    check_list_template = Column("CheckListTemplate", UnicodeText, nullable=True)
    is_active           = Column("IsActive", Boolean, nullable=False, default=True)
    created_at          = Column("CreatedAt", DateTime, server_default=func.now())
    instances = relationship("TaskInstance", back_populates="task", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("[Weight] BETWEEN 1 AND 10", name="CK_Task_Weight"),
        CheckConstraint("EstimatedMinutes > 0", name="CK_Task_EstimatedMinutes"),
        CheckConstraint("DeadlineOffset IS NULL OR DeadlineOffset >= 0", name="CK_Task_DeadlineOffset"),
        CheckConstraint(
            "(UserId IS NOT NULL AND ExternalRoleName IS NULL) OR "
            "(UserId IS NULL AND ExternalRoleName IS NOT NULL) OR "
            "(UserId IS NULL AND ExternalRoleName IS NULL)",
            name="CK_Task_Assignee",
        ),
        CheckConstraint(
            "DeadlineOffset IS NULL OR ScheduleRuleId IS NOT NULL",
            name="CK_Task_DeadlineOffset_OnlyRegular",
        ),
    )

# ============================================================
# Task_Instance — конкретное выполнение
# ============================================================
class TaskInstance(Base):
    __tablename__ = "Task_Instance"

    instance_id      = Column("InstanceId", BigInteger, primary_key=True, autoincrement=True)
    task_id          = Column("TaskId", Integer, ForeignKey("Task.TaskId"), nullable=False)
    assignee_user_id = Column("AssigneeUserId", Integer, ForeignKey("User.UserId"), nullable=True)
    status_id        = Column("StatusId", Integer, nullable=False)

    planned_start    = Column("PlannedStart", DateTime, nullable=True)
    planned_end      = Column("PlannedEnd", DateTime, nullable=True)
    actual_start     = Column("ActualStart", DateTime, nullable=True)
    actual_end       = Column("ActualEnd", DateTime, nullable=True)
    actual_minutes   = Column("ActualMinutes", Integer, nullable=True)

    is_taken         = Column("IsTaken", Boolean, nullable=False, default=False)

    created_at       = Column("CreatedAt", DateTime, server_default=func.now())

    # Связи
    task     = relationship("Task", back_populates="instances")
    assignee = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "(IsTaken = 0) OR (IsTaken = 1 AND AssigneeUserId IS NOT NULL)",
            name="CK_Task_Instance_Taken",
        ),
        CheckConstraint(
            "ActualStart IS NULL OR ActualEnd IS NULL OR ActualEnd >= ActualStart",
            name="CK_Task_Instance_ActualDates",
        ),
        CheckConstraint(
            "PlannedStart IS NULL OR PlannedEnd IS NULL OR PlannedEnd >= PlannedStart",
            name="CK_Task_Instance_PlannedDates",
        ),
        CheckConstraint(
            "ActualMinutes IS NULL OR ActualMinutes >= 0",
            name="CK_Task_Instance_ActualMinutes",
        ),
    )

    def __repr__(self):
        return f"<TaskInstance(instance_id={self.instance_id}, task_id={self.task_id}, status_id={self.status_id})>"

