from typing import Any, Optional


class Steps:
    START = "start"
    WAITING_NAME = "waiting_name"
    WAITING_LAST_NAME = "waiting_last_name"
    WAITING_PHONE = "waiting_phone"

    WAITING_NAME_ORG = "waiting_name_org"
    WAITING_ORG_CITY = "waiting_org_city"
    WAITING_ORG_TYPE = "waiting_org_type"

    WAITING_ORG_CODE = "waiting_org_code"

    PROFILE_WAITING_NAME = "profile_waiting_name"
    PROFILE_WAITING_LAST_NAME = "profile_waiting_last_name"
    PROFILE_WAITING_PHONE = "profile_waiting_phone"

    ANNOUNCEMENT_WAITING_TITLE = "announcement_waiting_title"
    ANNOUNCEMENT_WAITING_BODY = "announcement_waiting_body"
    ANNOUNCEMENT_WAITING_TARGET = "announcement_waiting_target"
    ANNOUNCEMENT_WAITING_USERS = "announcement_waiting_users"

    ORG_WAITING_NAME = "org_waiting_name"
    ORG_WAITING_CITY = "org_waiting_city"
    ORG_WAITING_TYPE = "org_waiting_type"

    ANN_WAITING_SEARCH_TITLE = "ann_waiting_search_title"
    ANN_WAITING_SEARCH_DATE = "ann_waiting_search_date"

    STAFF_WAITING_NUMBER_FIRE = "staff_waiting_number_fire"
    STAFF_WAITING_NUMBER_ROLE = "staff_waiting_number_role"
    STAFF_WAITING_NUMBER_NAME_ROLE = "staff_waiting_number_name_role"
    STAFF_WAITING_NAME_ORG_ROLE = "staff_waiting_name_org_role"

    TASK_CREATE_TITLE = "task_create_title"
    TASK_CREATE_DESC = "task_create_desc"
    TASK_CREATE_ASSIGNEE_USER = "task_create_assignee_user"
    TASK_CREATE_WEIGHT = "task_create_weight"
    TASK_CREATE_MINUTES = "task_create_minutes"

    TASK_EDIT_NUMBER = "task_edit_number"
    TASK_EDIT_TITLE = "task_edit_title"
    TASK_EDIT_DESC = "task_edit_desc"
    TASK_EDIT_WEIGHT = "task_edit_weight"
    TASK_EDIT_MINUTES = "task_edit_minutes"

    TASK_TITLE = "task_title"
    TASK_DESCRIPTION = "task_description"
    TASK_ASSIGNEE = "task_assignee"
    # TASK_EXTERNAL_ROLE = "task_external_role"
    TASK_RECURRENCE = "task_recurrence"

    # ветка A: разовая
    TASK_DEADLINE = "task_deadline"
    TASK_START_TIME_ASK = "task_start_time_ask"
    TASK_START_TIME = "task_start_time"

    # ветка B: постоянная
    TASK_WEEKDAYS = "task_weekdays"
    TASK_TIME = "task_time"                      # дедлайн (время суток)
    TASK_REGULAR_START_TIME = "task_regular_start_time"   # начало (время суток), необязательно


    TASK_PERIOD_ASK = "task_period_ask"
    TASK_PERIOD_START = "task_period_start"
    TASK_PERIOD_END = "task_period_end"

    # общие
    TASK_ESTIMATED_MINUTES = "task_estimated_minutes"
    TASK_WEIGHT = "task_weight"

    ANN_MY_WAITING_DATE = "ann_my_waiting_date"

    REPORT_WAITING_DATE_FROM = "report_waiting_date_from"
    REPORT_WAITING_DATE_TO = "report_waiting_date_to"

    MY_TASKS_WAITING_DATE = "my_tasks_waiting_date"  # если решим фильтровать по дате

    DONE = "done"


user_states: dict[int, dict[str, Any]] = {}


def get_state(user_id: int) -> dict:
    return user_states.setdefault(
        user_id,
        {"step": Steps.START, "data": {}},
    )


def get_step(user_id: int) -> str:
    return get_state(user_id)["step"]


def set_step(user_id: int, step: str) -> None:
    get_state(user_id)["step"] = step


def update_data(user_id: int, **kwargs: Any) -> None:
    get_state(user_id)["data"].update(kwargs)


def get_data(user_id: int, key: Optional[str] = None) -> Any:
    data = get_state(user_id)["data"]
    return data.get(key) if key else data


def clear_state(user_id: int) -> None:
    user_states.pop(user_id, None)